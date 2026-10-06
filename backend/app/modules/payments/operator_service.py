"""Operator API orchestration over immutable intents and trusted dispatch."""
from sqlalchemy import select
from fastapi import HTTPException
from app.modules.payments.models import PaymentIntent
from app.modules.payments.provider import PaymentAmount, PaymentRequest, OperationKind
from app.modules.payments.intents import persist_intent
from app.modules.payments.dispatch import dispatch_authorization, dispatch_parent_operation, dispatch_refund
from app.shared.exceptions import business_error, not_found


def require_operation_role(kind, user):
    if kind == "refund" and user["role"] != "responsable_institut":
        raise HTTPException(403, "Remboursement reserve a la responsable")


def prepare(db, institute_id, ticket_id, payload, user, binding):
    require_operation_role(payload.kind.value, user)
    reference = None
    if payload.kind is OperationKind.AUTHORIZE:
        if payload.parent_intent_id is not None:
            raise business_error("Une autorisation ne prend pas d'operation parente")
    else:
        parent_kind = "capture" if payload.kind is OperationKind.REFUND else "authorize"
        parent = db.scalar(select(PaymentIntent).where(PaymentIntent.id == payload.parent_intent_id,
            PaymentIntent.institute_id == institute_id, PaymentIntent.ticket_id == ticket_id,
            PaymentIntent.provider == binding.provider, PaymentIntent.account_id == binding.account_id,
            PaymentIntent.kind == parent_kind))
        if parent is None:
            raise not_found("Operation parente introuvable")
        if parent_kind == "authorize":
            from app.modules.payments.models import PaymentOutcome
            outcome = db.scalar(select(PaymentOutcome).where(PaymentOutcome.intent_id == parent.id,
                                                             PaymentOutcome.status == "authorized"))
            reference = outcome.provider_payment_id if outcome else None
        else:
            reference = parent.provider_payment_id
        if reference is None:
            raise business_error("Reference parente confirmee requise")
    try:
        request = PaymentRequest(institute_id, ticket_id, PaymentAmount(payload.amount, payload.currency),
                                 payload.idempotency_key, user["sub"])
        return persist_intent(db, request, payload.kind, binding.provider, binding.account_id, reference)
    except ValueError as failure:
        raise business_error("Termes de paiement invalides") from failure


def dispatch(session_factory, institute_id, intent_id, user, binding):
    with session_factory() as db:
        row = db.scalar(select(PaymentIntent).where(PaymentIntent.id == intent_id,
                                                     PaymentIntent.institute_id == institute_id))
        if row is None:
            raise not_found("Intention de paiement introuvable")
        require_operation_role(row.kind, user)
        if row.actor_id != user["sub"]:
            raise HTTPException(403, "Reprise reservee a l'identite de la demande initiale")
        kind = row.kind
    method = dispatch_authorization if kind == "authorize" else dispatch_refund if kind == "refund" else dispatch_parent_operation
    try:
        result = method(session_factory, institute_id, intent_id, binding)
    except HTTPException:
        raise
    except Exception as failure:
        # No transport or persistence error can establish provider failure.
        raise HTTPException(503, "Resultat a recuperer avec la meme intention de paiement") from failure
    return dict(id=intent_id, kind=kind, status=result.status.value, amount=result.value.amount, currency=result.value.currency)
