"""Resolve provider references through stored scoped facts, never caller claims."""
from sqlalchemy import select
from app.modules.payments.models import PaymentReference, PaymentIntent, PaymentOutcome, PaymentExecution
from app.modules.payments.provider import OperationKind
from app.shared.exceptions import business_error


def validate_parent_operation(db, request, kind, provider, account_id, reference, *, current_intent_id=None):
    """Caller holds institute lock. Reserve full authorization for capture/cancel.

    Refund requires captured settlement facts; authorization is not refundable cash.
    Partial/multiple capture is not configured and must not be inferred.
    """
    if kind is OperationKind.REFUND:
        from app.modules.payments.refunds import validate_refund_budget
        return validate_refund_budget(db, request, provider, account_id, reference)
    binding = db.get(PaymentReference, (provider, account_id, reference))
    parent = db.get(PaymentIntent, binding.intent_id) if binding else None
    if parent is None or (parent.institute_id, parent.ticket_id, parent.kind) != (
            request.institute_id, request.ticket_id, "authorize"):
        raise business_error("Autorisation parente de ce ticket et compte introuvable")
    fact = db.scalar(select(PaymentOutcome).where(PaymentOutcome.intent_id == parent.id,
                                                PaymentOutcome.status == "authorized"))
    execution = db.get(PaymentExecution, parent.id)
    if fact is None or execution is None or execution.released_at is not None:
        raise business_error("Autorisation confirmee et encore protegee requise")
    if (fact.amount, fact.currency) != (request.value.amount, request.value.currency):
        raise business_error("Montant et devise doivent correspondre a l'autorisation complete")
    reserved = select(PaymentIntent.id).where(
        PaymentIntent.institute_id == request.institute_id,
        PaymentIntent.provider == provider, PaymentIntent.account_id == account_id,
        PaymentIntent.provider_payment_id == reference,
        PaymentIntent.kind.in_(["capture", "cancel"]))
    from app.modules.payments.models import ParentOperationOutcome
    failed = select(ParentOperationOutcome.id).where(
        ParentOperationOutcome.intent_id == PaymentIntent.id,
        ParentOperationOutcome.status == "failed").exists()
    reserved = reserved.where(~failed)
    if current_intent_id:
        reserved = reserved.where(PaymentIntent.id != current_intent_id)
    if db.scalar(reserved):
        raise business_error("Une capture ou annulation est deja reservee; recuperer son resultat")
    return parent
