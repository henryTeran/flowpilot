"""Read authoritative sources for an explicit attribution preview, never retain a link."""
from pydantic import AwareDatetime, model_validator
from sqlalchemy import select
from app.modules.crm.metrics import Fact, Identifier, BillingWindow, ClosedTicketFact
from app.modules.crm.policies import Reason, Key
from app.modules.crm.billing import amount_fact
from app.modules.marketing import conversions, dispatch_intents, dispatch_outcomes, campaign_originals, provider
from app.modules.customers.repository import require_customer
from app.modules.tickets.models import QueueTicket
from app.modules.tickets.repository import lock_institute
from app.shared.exceptions import business_error, not_found
from app.shared.time import utcnow, explicit_utc_instant
from typing import Literal


class Request(Fact):
    intent_id: Identifier
    expected_fingerprint: provider.Fingerprint
    authorization_id: Identifier
    accepted_outcome_id: Identifier
    ticket_id: Identifier
    start: AwareDatetime
    end: AwareDatetime
    reason: Reason
    idempotency_key: Key

    @model_validator(mode="after")
    def positive_window(self):
        if self.start >= self.end:
            raise ValueError("An explicit positive attribution window is required")
        return self


class Preview(Fact):
    request: Request
    attribution: conversions.Attribution
    retained: Literal[False] = False


def validate(db, institute, payload, actor):
    payload = Request.model_validate(payload.model_dump())
    lock_institute(db, institute)
    at = utcnow()
    intent = dispatch_intents.require(db, institute, payload.intent_id)
    if intent.request_fingerprint != payload.expected_fingerprint:
        raise business_error("Selected attribution intent fingerprint changed")
    authorization = campaign_originals.require(db, institute, payload.authorization_id)
    accepted = dispatch_outcomes.require(db, institute, intent.id, payload.accepted_outcome_id)
    customer = intent.request.customer_id
    require_customer(db, institute, customer)
    ticket = db.scalar(select(QueueTicket).where(QueueTicket.institute_id == institute,
        QueueTicket.id == payload.ticket_id, QueueTicket.customer_id == customer).execution_options(populate_existing=True))
    if ticket is None: raise not_found("Owned recipient billing ticket not found")
    if ticket.status != "paid" or ticket.paid_at is None:
        raise business_error("Attribution requires a recorded paid ticket with an explicit paid time")
    try:
        minor, quality = amount_fact(ticket.total_amount)
        fact = ClosedTicketFact(institute_id=institute, customer_id=customer, ticket_id=ticket.id,
            closed_at=explicit_utc_instant(ticket.paid_at), captured_at=at,
            currency=ticket.currency if ticket.currency in ("CHF", "EUR") else None,
            amount_minor=minor, amount_quality=quality)
        window = BillingWindow(institute_id=institute, customer_id=customer,
            start=payload.start, end=payload.end, captured_at=at)
        attribution = conversions.Attribution(intent=intent, authorization=authorization, accepted=accepted,
            ticket=fact, window=window, actor_id=actor, reason=payload.reason, idempotency_key=payload.idempotency_key)
    except (ValueError, TypeError):
        raise business_error("Attribution sources or observed window are incoherent") from None
    return Preview(request=payload, attribution=attribution)
