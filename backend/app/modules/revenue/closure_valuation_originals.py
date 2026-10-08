"""Independent retained historical-rate decisions; never causal-loss totals."""
from types import SimpleNamespace
from typing import Literal
from pydantic import AwareDatetime, field_validator, model_validator
from sqlalchemy import select
from app.modules.crm.metrics import Fact, Identifier, Count
from app.modules.crm.policies import Key
from app.modules.revenue import booking_valuation as values, booking_references as refs, closures
from app.modules.revenue.billing import Window
from app.modules.revenue.scenario_originals import Envelope, fingerprint
from app.modules.revenue.models import ClosureValuationOriginal as Row
from app.modules.appointments.models import BookingEvent
from app.modules.tickets.repository import lock_institute
from app.shared.exceptions import business_error, not_found
from app.shared.ids import new_id
from app.shared.time import utcnow, explicit_utc_instant


class Declaration(Fact):
    valuation: values.Request
    idempotency_key: Key

    @model_validator(mode="after")
    def exact_reason(self):
        if self.valuation.reason != self.valuation.reason.strip() or len(self.valuation.reason) < 3:
            raise ValueError("An exact meaningful valuation reason is required")
        return self


class ReferenceEvent(Fact):
    id: Identifier
    institute_id: Identifier
    appointment_id: Identifier
    event_type: Literal["created", "modified"]
    occurred_at: AwareDatetime
    actor_id: str | None
    before: closures.BookingSnapshot | None
    after: closures.BookingSnapshot


class Original(values.Calculation):
    id: Identifier
    institute_id: Identifier
    appointment_id: Identifier
    idempotency_key: Key
    created_at: AwareDatetime
    reference_event: ReferenceEvent
    retained: Literal[True] = True

    @field_validator("retained", mode="before")
    @classmethod
    def retained_only(cls, value):
        if value is not True:
            raise ValueError("An original must explicitly be retained")
        return value


class Audit(Fact):
    institute_id: Identifier
    captured_at: AwareDatetime
    offset: Count
    limit: Count
    total: Count
    originals: tuple[Envelope, ...]
    full_original_cohort_verified: Literal[True] = True
    causal_loss_proven: Literal[False] = False
    action_executed: Literal[False] = False

    @field_validator("full_original_cohort_verified", "causal_loss_proven", "action_executed", mode="before")
    @classmethod
    def strict_claims(cls, value, info):
        if value is not (True if info.field_name == "full_original_cohort_verified" else False):
            raise ValueError("Retained decisions cannot prove causal loss or actions")
        return value


def verify(row, institute, now):
    try:
        if row.institute_id != institute or fingerprint(row.original) != row.fingerprint:
            raise ValueError("Original scope or fingerprint differs")
        o = Original.model_validate(row.original)
        if (o.id, o.institute_id, o.appointment_id, o.actor_id, o.idempotency_key, o.created_at) != (
            row.id, institute, row.appointment_id, row.actor_id, row.idempotency_key, explicit_utc_instant(row.created_at)) \
            or o.created_at != o.evidence.captured_at or o.created_at > now or o.id != o.id.strip() \
            or not o.actor_id or o.actor_id != o.actor_id.strip() or len(o.actor_id) > 160 or any(ord(c) < 32 for c in o.actor_id):
            raise ValueError("Stored identity/actor/capture differ")
        declaration = Declaration(valuation=o.request, idempotency_key=o.idempotency_key)
        if declaration.model_dump(mode="json") != dict(valuation=row.original["request"], idempotency_key=row.original["idempotency_key"]):
            raise ValueError("Declared terms cannot be normalized on reread")
        event = SimpleNamespace(**o.reference_event.model_dump())
        if (event.institute_id, event.appointment_id) != (institute, o.appointment_id):
            raise ValueError("Retained reference event scope differs")
        event.price_reference = o.reference.model_dump(mode="json")
        refs.verify(event, institute, o.appointment_id, o.created_at)
        terms = refs.Terms.model_validate(o.reference.terms)
        e = o.evidence
        if (e.institute_id, e.appointment_id, e.event_id) != (institute, o.appointment_id, o.request.closure_event_id) \
            or o.request.reference_event_id != event.id or o.request.expected_fingerprint != o.reference.fingerprint \
            or terms.occurred_at > e.occurred_at or terms.service_id != e.after.service_id:
            raise ValueError("Selected source identity or chronology differs")
        # Validate the retained terminal transition, not today's mutable booking.
        closures.verify(e, e.after, Window(institute_id=institute, start=e.occurred_at, end=o.created_at, captured_at=o.created_at))
        value, reason = values.value_for(terms, o.request.rate)
        if o.estimated_value != value or o.unavailable_reason != reason:
            raise ValueError("Retained historical-rate calculation differs")
        return Envelope(original=row.original, fingerprint=row.fingerprint)
    except (ValueError, TypeError, KeyError, OverflowError) as error:
        raise business_error("Retained closure valuation requires verification") from error


def _row(db, institute, field, value):
    return db.scalar(select(Row).where(Row.institute_id == institute, field == value).execution_options(populate_existing=True))


def create(db, institute, appointment, payload, actor):
    try:
        payload = Declaration.model_validate(payload.model_dump())
        if not isinstance(actor, str) or not actor or actor != actor.strip() or len(actor) > 160 or any(ord(c) < 32 for c in actor):
            raise ValueError("A signed valuation actor is required")
        lock_institute(db, institute)
        now = utcnow()
        row = _row(db, institute, Row.idempotency_key, payload.idempotency_key)
        if row:
            result = verify(row, institute, now)
            old = Original.model_validate(result.original)
            if old.actor_id != actor or old.appointment_id != appointment or Declaration(valuation=old.request, idempotency_key=old.idempotency_key) != payload:
                raise business_error("The valuation key retains its original request, appointment and actor")
            return result
        preview = values.preview(db, institute, appointment, payload.valuation, actor, captured_at=now)
        event = db.scalar(select(BookingEvent).where(BookingEvent.institute_id == institute, BookingEvent.appointment_id == appointment,
            BookingEvent.id == payload.valuation.reference_event_id).execution_options(populate_existing=True))
        proof = ReferenceEvent(**{k: explicit_utc_instant(event.occurred_at) if k == "occurred_at" else getattr(event, k) for k in ReferenceEvent.model_fields})
        original = Original(**preview.model_dump(exclude={"retained"}), id=new_id("closure_valuation"), institute_id=institute,
            appointment_id=appointment, idempotency_key=payload.idempotency_key, created_at=now, reference_event=proof)
        raw = original.model_dump(mode="json")
        row = Row(id=original.id, institute_id=institute, appointment_id=appointment, actor_id=actor, idempotency_key=payload.idempotency_key,
            created_at=now, original=raw, fingerprint=fingerprint(raw))
        db.add(row); db.flush()
        result = verify(row, institute, now)
        db.commit()
        return result
    except ValueError as error:
        db.rollback()
        raise business_error("Explicit valuation declaration and sources require verification") from error
    except Exception:
        db.rollback()
        raise


def by_key(db, institute, key):
    if not isinstance(key, str) or not key or key != key.strip() or len(key) > 120:
        raise business_error("An exact valuation recovery key is required")
    lock_institute(db, institute)
    row = _row(db, institute, Row.idempotency_key, key)
    return verify(row, institute, utcnow()) if row else None


def require(db, institute, identifier):
    lock_institute(db, institute)
    row = _row(db, institute, Row.id, identifier)
    if row is None:
        raise not_found("Retained closure valuation not found")
    return verify(row, institute, utcnow())


def audit(db, institute, offset=0, limit=20):
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 50:
        raise business_error("Invalid valuation audit page bounds")
    lock_institute(db, institute)
    now, total, rows = utcnow(), 0, []
    for row in db.scalars(select(Row).where(Row.institute_id == institute).order_by(Row.created_at, Row.id)
        .execution_options(yield_per=100, populate_existing=True)):
        result = verify(row, institute, now)
        if offset <= total < offset+limit:
            rows.append(result)
        total += 1
    return Audit(institute_id=institute, captured_at=now, offset=offset, limit=limit, total=total, originals=tuple(rows))
