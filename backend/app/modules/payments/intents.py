"""Persist immutable operation requests before any adapter I/O."""
from sqlalchemy import select
from app.modules.payments.models import PaymentIntent
from app.modules.payments.provider import PaymentRequest, PaymentAmount, OperationKind, identifier
from app.modules.tickets.models import QueueTicket
from app.modules.tickets.repository import lock_institute
from app.shared.exceptions import business_error, not_found
from app.shared.ids import new_id
from app.shared.time import utcnow


def persist_intent(db, request: PaymentRequest, kind: OperationKind, provider: str,
                   account_id: str, provider_payment_id: str | None = None):
    if not isinstance(request, PaymentRequest) or not isinstance(kind, OperationKind):
        raise ValueError("Typed request and operation required")
    identifier(provider, 80); identifier(account_id, 80)
    if provider_payment_id is not None:
        identifier(provider_payment_id, 240)
    elif kind is not OperationKind.AUTHORIZE:
        raise ValueError("Stored provider reference required")
    lock_institute(db, request.institute_id)
    terms = dict(ticket_id=request.ticket_id, provider=provider, account_id=account_id,
        kind=kind.value, amount=request.value.amount, currency=request.value.currency,
        provider_payment_id=provider_payment_id, actor_id=request.actor_id)
    old = db.scalar(select(PaymentIntent).where(PaymentIntent.institute_id == request.institute_id,
                                               PaymentIntent.idempotency_key == request.idempotency_key))
    if old:
        if any(getattr(old, key) != value for key, value in terms.items()):
            raise business_error("Cette cle appartient a une autre operation de paiement")
        return old
    ticket = db.get(QueueTicket, request.ticket_id)
    if ticket is None or ticket.institute_id != request.institute_id:
        raise not_found("Ticket de paiement introuvable")
    db.refresh(ticket)
    if ticket.currency != request.value.currency:
        raise business_error("Devise confirmee correspondante requise pour le paiement")
    row = PaymentIntent(id=new_id("pi"), institute_id=request.institute_id,
        idempotency_key=request.idempotency_key, created_at=utcnow(), **terms)
    db.add(row); db.commit(); db.refresh(row)
    return row


def original_request(row: PaymentIntent):
    return PaymentRequest(row.institute_id, row.ticket_id, PaymentAmount(row.amount, row.currency),
                          row.idempotency_key, row.actor_id)
