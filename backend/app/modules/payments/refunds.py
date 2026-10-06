"""Refund reservation budget from captured checkout facts, never invoice totals."""
from decimal import Decimal, localcontext
from sqlalchemy import select
from app.modules.payments.models import PaymentIntent, ParentOperationOutcome, CaptureApplication
from app.shared.exceptions import business_error


def validate_refund_budget(db, request, provider, account_id, reference):
    """Caller holds institute lock; every unresolved request reserves its amount.

    Failed refund release requires a future verified refund fact. Do not abandon
    reservations on timeout. Gift-funded value is not part of external capture.
    """
    capture = db.scalar(select(PaymentIntent).join(ParentOperationOutcome,
                    ParentOperationOutcome.intent_id == PaymentIntent.id).where(
        PaymentIntent.institute_id == request.institute_id, PaymentIntent.ticket_id == request.ticket_id,
        PaymentIntent.provider == provider, PaymentIntent.account_id == account_id,
        PaymentIntent.provider_payment_id == reference, PaymentIntent.kind == "capture",
        ParentOperationOutcome.status == "captured"))
    application = db.get(CaptureApplication, request.ticket_id)
    if capture is None or application is None or application.intent_id != capture.id:
        raise business_error("Fait de capture confirme applique en caisse requis avant remboursement")
    if capture.currency != request.value.currency:
        raise business_error("Devise du remboursement identique a la capture requise")
    amounts = db.scalars(select(PaymentIntent.amount).where(
        PaymentIntent.institute_id == request.institute_id, PaymentIntent.ticket_id == request.ticket_id,
        PaymentIntent.provider == provider, PaymentIntent.account_id == account_id,
        PaymentIntent.provider_payment_id == reference, PaymentIntent.kind == "refund"))
    with localcontext() as context:
        context.prec = 28
        reserved = sum(amounts, Decimal("0"))
        if reserved + request.value.amount > capture.amount:
            raise business_error("Montant superieur au budget remboursable restant de la capture")
    return capture
