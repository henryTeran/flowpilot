"""Bounded authoritative recorded paid tickets for an explicitly accepted intent."""
from datetime import timezone
from pydantic import AwareDatetime, model_validator
from sqlalchemy import select, func
from app.modules.crm.metrics import Fact, Identifier, BillingWindow, ClosedTicketFact
from app.modules.crm.billing import amount_fact
from app.modules.marketing import catalogs, dispatch_intents, dispatch_outcomes, provider
from app.modules.customers.repository import require_customer
from app.modules.tickets.models import QueueTicket
from app.shared.time import utcnow, explicit_utc_instant
from app.shared.exceptions import business_error


class Request(Fact):
    intent_id: Identifier
    expected_fingerprint: provider.Fingerprint
    accepted_outcome_id: Identifier
    start: AwareDatetime
    end: AwareDatetime

    @model_validator(mode="after")
    def chronology(self):
        if self.start >= self.end: raise ValueError("Positive explicit window required")
        return self


class Read(Fact):
    request: Request
    window: BillingWindow
    page: catalogs.Page[ClosedTicketFact]


def read(db, institute, payload, offset=0, limit=20):
    payload = Request.model_validate(payload.model_dump())
    catalogs.bounds(db, institute, offset, limit)
    at = utcnow()
    intent = dispatch_intents.require(db, institute, payload.intent_id)
    outcome = dispatch_outcomes.require(db, institute, intent.id, payload.accepted_outcome_id)
    result = provider.validate_result(intent.submission, outcome.request.result)
    if intent.request_fingerprint != payload.expected_fingerprint or result.status != "accepted":
        raise business_error("An exact accepted intent observation is required")
    customer = intent.request.customer_id
    require_customer(db, institute, customer)
    try:
        window = BillingWindow(institute_id=institute, customer_id=customer,
            start=payload.start, end=payload.end, captured_at=at)
        if result.observed_at > window.start or outcome.created_at > at:
            raise ValueError("Unobserved or pre-acceptance window")
    except ValueError:
        raise business_error("An observed post-acceptance billing window is required") from None
    scope = (QueueTicket.institute_id == institute, QueueTicket.customer_id == customer,
        QueueTicket.status == "paid", QueueTicket.paid_at >= window.start.astimezone(timezone.utc),
        QueueTicket.paid_at < window.end.astimezone(timezone.utc))
    total = db.scalar(select(func.count()).select_from(QueueTicket).where(*scope))
    rows = db.scalars(select(QueueTicket).where(*scope).order_by(QueueTicket.paid_at, QueueTicket.id)
        .offset(offset).limit(limit).execution_options(populate_existing=True))
    items = []
    try:
        for ticket in rows:
            minor, quality = amount_fact(ticket.total_amount)
            items.append(ClosedTicketFact(institute_id=institute, customer_id=customer, ticket_id=ticket.id,
                closed_at=explicit_utc_instant(ticket.paid_at), captured_at=at,
                currency=ticket.currency if ticket.currency in ("CHF", "EUR") else None,
                amount_minor=minor, amount_quality=quality))
    except (ValueError, TypeError):
        raise business_error("Recorded billing source is incoherent") from None
    return Read(request=payload, window=window, page=catalogs.Page[ClosedTicketFact](institute_id=institute,
        total=total, offset=offset, limit=limit, items=tuple(items)))
