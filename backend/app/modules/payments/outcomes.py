"""Internal adapter observations, never client-supplied settlement claims."""
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.modules.payments.models import PaymentIntent, PaymentExecution, PaymentOutcome, PaymentReference
from app.modules.payments.intents import original_request
from app.modules.payments.provider import OperationKind, ProviderStatus, validate_result
from app.modules.tickets.repository import lock_institute
from app.shared.exceptions import business_error, not_found
from app.shared.ids import new_id
from app.shared.time import utcnow


def record_authorization_outcome(db, institute_id, intent_id, provider, account_id, result):
    """Called only after the configured adapter authenticates its response.

    No public route exposes this method. Caller account must be its trusted binding,
    not a request body field. Authorized funds remain frozen until capture/cancel.
    """
    lock_institute(db, institute_id)
    intent = db.scalar(select(PaymentIntent).where(PaymentIntent.id == intent_id,
                                                  PaymentIntent.institute_id == institute_id))
    if intent is None:
        raise not_found("Intention de paiement introuvable")
    if (intent.provider, intent.account_id, intent.kind) != (provider, account_id, "authorize"):
        raise business_error("Prestataire, compte ou operation incompatible")
    execution = db.get(PaymentExecution, intent_id)
    if execution is None:
        raise business_error("Execution durable requise avant resultat prestataire")
    validate_result(original_request(intent), OperationKind.AUTHORIZE, result, intent.provider_payment_id)
    rows = list(db.scalars(select(PaymentOutcome).where(PaymentOutcome.intent_id == intent_id)))
    if any(row.provider_payment_id != result.provider_payment_id for row in rows):
        raise business_error("Reference prestataire differente du resultat initial")
    old = next((row for row in rows if row.status == result.status.value), None)
    if old is not None:
        return old
    if any(row.status != "pending" for row in rows):
        raise business_error("Le resultat terminal ne peut pas etre remplace")
    reference = db.get(PaymentReference, (provider, account_id, result.provider_payment_id))
    if reference is not None and reference.intent_id != intent_id:
        raise business_error("Reference prestataire deja liee a une autre intention")
    if reference is None:
        db.add(PaymentReference(provider=provider, account_id=account_id,
                 provider_payment_id=result.provider_payment_id, intent_id=intent_id))
    row = PaymentOutcome(id=new_id("po"), intent_id=intent_id, status=result.status.value,
             provider_payment_id=result.provider_payment_id, amount=result.value.amount,
             currency=result.value.currency, observed_at=utcnow())
    db.add(row)
    if result.status is ProviderStatus.FAILED:
        execution.released_at = row.observed_at
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise business_error("Reference prestataire deja enregistree; verifier le resultat")
    db.refresh(row)
    return row
