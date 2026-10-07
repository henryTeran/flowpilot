"""Full-cohort proof and exact recorded commercial value, never causal loss."""
from datetime import timezone
from typing import Literal, Annotated
from pydantic import AwareDatetime, Field, StringConstraints, field_validator, model_validator
from sqlalchemy import select, func
from app.modules.crm.metrics import Fact, Identifier, Minor, Count
from app.modules.revenue.billing import Window, AmountGroup, _empty, _add, _amount
from app.modules.tickets.models import QueueEvent, QueueTicket
from app.modules.tickets.cancellation_terms import fingerprint
from app.modules.tickets.repository import lock_institute
from app.modules.workforce.schemas import MatrixPage
from app.shared.exceptions import business_error
from app.shared.time import explicit_utc_instant, utcnow


class Line(Fact):
    id: Identifier
    service_id: Identifier
    quantity: int = Field(strict=True, gt=0)
    duration_minutes: int = Field(strict=True, ge=0)
    category: str
    unit_minor: Minor | None
    unit_quality: Literal["known", "missing", "invalid"]
    total_minor: Minor | None
    total_quality: Literal["known", "missing", "invalid"]
    removed_at: AwareDatetime | None

    @model_validator(mode="after")
    def coherent(self):
        if (self.unit_quality == "known") != (self.unit_minor is not None) or (self.total_quality == "known") != (self.total_minor is not None):
            raise ValueError("Historical line amount diagnostics must agree")
        return self


class Terms(Fact):
    institute_id: Identifier
    ticket_id: Identifier
    customer_id: Identifier | None
    previous_status: Literal["waiting", "assigned", "ready_for_checkout", "in_checkout"]
    status: Literal["cancelled"]
    occurred_at: AwareDatetime
    actor_id: Annotated[str, StringConstraints(min_length=1, max_length=160)] | None
    currency: Literal["CHF", "EUR"] | None
    amount_minor: Minor | None
    amount_quality: Literal["known", "missing", "invalid"]
    lines: tuple[Line, ...]
    basis: Literal["recorded_commercial_terms_at_cancellation"]
    realized_revenue: Literal[False]
    causal_loss_proven: Literal[False]

    @field_validator("realized_revenue", "causal_loss_proven", mode="before")
    @classmethod
    def no_claim(cls, value):
        if value is not False:
            raise ValueError("Retained commercial value cannot prove realized revenue or causal loss")
        return value

    @model_validator(mode="after")
    def coherent(self):
        if (self.amount_quality == "known") != (self.amount_minor is not None):
            raise ValueError("Historical basket amount diagnostics must agree")
        ids = [line.id for line in self.lines]
        if ids != sorted(set(ids)) or any(line.removed_at and line.removed_at > self.occurred_at for line in self.lines):
            raise ValueError("Historical lines must be unique, ordered and already removed at capture")
        return self


class Envelope(Fact):
    # Preserve the original JSON spelling of aware instants. Typed projection
    # would rewrite +00:00 to Z and invalidate the returned original fingerprint.
    terms: dict
    fingerprint: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class Value(Fact):
    currency: Literal["CHF", "EUR"]
    amount_minor: Minor
    basis: Literal["recorded_cancelled_commercial_value"] = "recorded_cancelled_commercial_value"


class Evidence(Fact):
    institute_id: Identifier
    ticket_id: Identifier
    event_id: int = Field(strict=True, gt=0)
    occurred_at: AwareDatetime
    captured_at: AwareDatetime
    original: Envelope | None


class Opportunity(Fact):
    type: Literal["review_cancelled_walk_in"] = "review_cancelled_walk_in"
    evidence: Evidence
    estimated_value: Value | None
    confidence: Literal["retained_commercial_terms_not_causal_loss", "legacy_cancellation_unpriced"]
    recommended_action: Literal["review_cancellation_and_source_terms_before_any_recovery"] = "review_cancellation_and_source_terms_before_any_recovery"
    action_executed: Literal[False] = False

    @field_validator("action_executed", mode="before")
    @classmethod
    def no_action(cls, value):
        if value is not False:
            raise ValueError("A cancellation review cannot execute recovery")
        return value


class Read(Fact):
    window: Window
    basis: Literal["walk_in_cancellation_event_time"] = "walk_in_cancellation_event_time"
    page: MatrixPage
    opportunities: tuple[Opportunity, ...]
    retained_terms_count: Count
    legacy_unpriced_count: Count
    retained_amounts: tuple[AmountGroup, ...]
    cancelled_revenue: None = None
    causal_loss_proven: Literal[False] = False

    @field_validator("causal_loss_proven", mode="before")
    @classmethod
    def no_claim(cls, value):
        if value is not False:
            raise ValueError("Cancellation value is not proven revenue loss")
        return value


def original(raw, institute, ticket, previous, at):
    # Digest the entire stored JSON before typed projection; extra fields cannot
    # be dropped before checking the original full-frame identity.
    if not isinstance(raw, dict) or set(raw) != {"terms", "fingerprint"} or fingerprint(raw["terms"]) != raw["fingerprint"]:
        raise ValueError("Retained cancellation fingerprint differs")
    value = Envelope.model_validate(raw)
    terms = Terms.model_validate(value.terms)
    if (terms.institute_id, terms.ticket_id, terms.previous_status, terms.occurred_at) != (institute, ticket, previous, at):
        raise ValueError("Retained cancellation event binding differs")
    return value


def read(db, institute, start, end, offset=0, limit=20):
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 50:
        raise business_error("Invalid cancellation page bounds")
    lock_institute(db, institute)
    try:
        window = Window(institute_id=institute, start=start, end=end, captured_at=utcnow())
    except ValueError as error:
        raise business_error("An explicit positive observed cancellation period is required") from error
    counts = select(QueueEvent.ticket_id.label("ticket"), func.count().label("count")).where(
        QueueEvent.institute_id == institute, QueueEvent.event_type == "queue.cancelled").group_by(QueueEvent.ticket_id).subquery()
    source = select(QueueEvent, QueueTicket, counts.c.count).outerjoin(QueueTicket,
        (QueueTicket.id == QueueEvent.ticket_id) & (QueueTicket.institute_id == QueueEvent.institute_id)) \
        .join(counts, counts.c.ticket == QueueEvent.ticket_id).where(QueueEvent.institute_id == institute,
            QueueEvent.event_type == "queue.cancelled", QueueEvent.occurred_at >= window.start.astimezone(timezone.utc),
            QueueEvent.occurred_at < window.end.astimezone(timezone.utc)).order_by(QueueEvent.occurred_at, QueueEvent.id)
    total = retained = legacy = 0
    rows, groups = [], {}
    try:
        for event, ticket, count in db.execute(source.execution_options(yield_per=100, populate_existing=True)):
            at = explicit_utc_instant(event.occurred_at)
            if ticket is None or ticket.status != "cancelled" or event.status != "cancelled" or count != 1 \
                    or event.previous_status not in {"waiting", "assigned", "ready_for_checkout", "in_checkout"}:
                raise ValueError("A unique owned terminal cancellation event is required")
            saved = original(event.cancellation_terms, institute, ticket.id, event.previous_status, at) if event.cancellation_terms is not None else None
            amount = None
            if saved:
                retained += 1
                terms = Terms.model_validate(saved.terms)
                _add(groups.setdefault(terms.currency, _empty()), terms)
                if terms.currency is not None and terms.amount_quality == "known":
                    amount = Value(currency=terms.currency, amount_minor=terms.amount_minor)
            else:
                legacy += 1
            if offset <= total < offset+limit:
                rows.append(Opportunity(evidence=Evidence(institute_id=institute, ticket_id=ticket.id, event_id=event.id,
                    occurred_at=at, captured_at=window.captured_at, original=saved), estimated_value=amount,
                    confidence="retained_commercial_terms_not_causal_loss" if saved else "legacy_cancellation_unpriced"))
            total += 1
    except (ValueError, TypeError, KeyError) as error:
        raise business_error("Retained cancellation sources require verification") from error
    return Read(window=window, page=MatrixPage(offset=offset, limit=limit, total=total), opportunities=tuple(rows),
        retained_terms_count=retained, legacy_unpriced_count=legacy,
        retained_amounts=tuple(_amount(currency, groups[currency]) for currency in sorted(groups, key=lambda value: value or "")))
