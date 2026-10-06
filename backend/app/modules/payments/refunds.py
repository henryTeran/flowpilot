"""Refund reservation budget from captured checkout facts, never invoice totals."""
from decimal import Decimal, localcontext
from sqlalchemy import select
from app.modules.payments.models import PaymentIntent, ParentOperationOutcome, CaptureApplication
from app.shared.exceptions import business_error


def validate_refund_budget(db, request, provider, account_id, reference, *, current_intent_id=None):
    """Caller holds institute lock; every unresolved request reserves its amount.

    Only a persisted verified failure releases the reservation. Do not abandon
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
    from app.modules.payments.models import RefundOutcome
    failed = select(RefundOutcome.id).where(RefundOutcome.intent_id == PaymentIntent.id,
                                            RefundOutcome.status == "failed").exists()
    reservations = select(PaymentIntent.amount).where(
        PaymentIntent.institute_id == request.institute_id, PaymentIntent.ticket_id == request.ticket_id,
        PaymentIntent.provider == provider, PaymentIntent.account_id == account_id,
        PaymentIntent.provider_payment_id == reference, PaymentIntent.kind == "refund", ~failed)
    if current_intent_id is not None:
        from app.modules.payments.intents import original_request
        current = db.get(PaymentIntent, current_intent_id)
        if current is None or original_request(current) != request or (current.kind, current.provider, current.account_id, current.provider_payment_id) != ("refund", provider, account_id, reference):
            raise business_error("Reservation initiale correspondante requise")
        reservations = reservations.where(PaymentIntent.id != current_intent_id)
    amounts = db.scalars(reservations)
    with localcontext() as context:
        context.prec = 28
        reserved = sum(amounts, Decimal("0"))
        if reserved + request.value.amount > capture.amount:
            raise business_error("Montant superieur au budget remboursable restant de la capture")
    return capture



def seal_refund(db, institute_id, intent_id):
    from app.modules.payments.models import RefundExecution
    from app.modules.payments.intents import original_request
    from app.modules.tickets.repository import lock_institute
    from app.shared.exceptions import not_found
    from app.shared.time import utcnow
    lock_institute(db, institute_id)
    intent = db.scalar(select(PaymentIntent).where(PaymentIntent.id == intent_id,
                                                  PaymentIntent.institute_id == institute_id))
    if intent is None:
        raise not_found("Intention de paiement introuvable")
    if intent.kind != "refund":
        raise business_error("Intention de remboursement requise")
    request = original_request(intent)
    if db.get(RefundExecution, intent_id) is not None:
        return request
    capture = validate_refund_budget(db, request, intent.provider, intent.account_id,
                                     intent.provider_payment_id, current_intent_id=intent_id)
    db.add(RefundExecution(intent_id=intent_id, capture_intent_id=capture.id, sealed_at=utcnow()))
    db.commit()
    return request


def record_refund_outcome(db, institute_id, intent_id, provider, account_id, result):
    from app.modules.payments.models import RefundExecution, RefundOutcome
    from app.modules.payments.intents import original_request
    from app.modules.payments.provider import OperationKind, validate_result
    from app.modules.tickets.repository import lock_institute
    from app.shared.exceptions import not_found
    from app.shared.ids import new_id
    from app.shared.time import utcnow
    lock_institute(db, institute_id)
    intent = db.scalar(select(PaymentIntent).where(PaymentIntent.id == intent_id,
                                                  PaymentIntent.institute_id == institute_id))
    if intent is None:
        raise not_found("Intention de paiement introuvable")
    if (intent.kind, intent.provider, intent.account_id) != ("refund", provider, account_id):
        raise business_error("Compte ou operation incompatible")
    if db.get(RefundExecution, intent_id) is None:
        raise business_error("Execution durable requise avant resultat prestataire")
    validate_result(original_request(intent), OperationKind.REFUND, result, intent.provider_payment_id)
    rows = list(db.scalars(select(RefundOutcome).where(RefundOutcome.intent_id == intent_id)))
    old = next((row for row in rows if row.status == result.status.value), None)
    if old is not None:
        return old
    if any(row.status != "pending" for row in rows):
        raise business_error("Le resultat terminal ne peut pas etre remplace")
    row = RefundOutcome(id=new_id("rpo"), intent_id=intent_id, status=result.status.value,
          provider_payment_id=result.provider_payment_id, amount=result.value.amount,
          currency=result.value.currency, observed_at=utcnow())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
