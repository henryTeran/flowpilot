"""Authenticate raw input through server-selected adapter, then apply atomically."""
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.modules.payments.dispatch import ProviderBinding
from app.modules.payments.provider import RawWebhook, VerifiedWebhook
from app.modules.payments.models import PaymentIntent, WebhookReceipt
from app.modules.tickets.repository import lock_institute
from app.shared.exceptions import business_error
from app.shared.time import utcnow


def receive_webhook(session_factory, binding: ProviderBinding, raw: RawWebhook):
    if not isinstance(binding, ProviderBinding) or not isinstance(raw, RawWebhook):
        raise ValueError("Trusted binding and raw webhook required")
    event = binding.adapter.webhook(raw)  # Authenticate before opening a SQL session.
    if not isinstance(event, VerifiedWebhook) or event.operation_key is None:
        raise business_error("Evenement authentifie et operation explicite requis")
    with session_factory() as db:
        lock_institute(db, binding.institute_id)
        intent = db.scalar(select(PaymentIntent).where(
            PaymentIntent.institute_id == binding.institute_id,
            PaymentIntent.provider == binding.provider, PaymentIntent.account_id == binding.account_id,
            PaymentIntent.idempotency_key == event.operation_key))
        if intent is None:
            raise business_error("Operation prestataire de ce compte introuvable")
        terms = dict(institute_id=binding.institute_id, intent_id=intent.id,
                     status=event.result.status.value, provider_payment_id=event.result.provider_payment_id,
                     amount=event.result.value.amount, currency=event.result.value.currency)
        old = db.get(WebhookReceipt, (binding.provider, binding.account_id, event.event_id))
        if old is not None:
            if any(getattr(old, field) != value for field, value in terms.items()):
                raise business_error("Cet evenement appartient a un autre resultat")
            return event.result
        from app.modules.payments.outcomes import record_authorization_outcome, record_parent_outcome
        from app.modules.payments.refunds import record_refund_outcome
        writer = (record_authorization_outcome if intent.kind == "authorize" else
                  record_refund_outcome if intent.kind == "refund" else record_parent_outcome)
        try:
            writer(db, binding.institute_id, intent.id, binding.provider, binding.account_id, event.result, commit=False)
            db.add(WebhookReceipt(provider=binding.provider, account_id=binding.account_id,
                   event_id=event.event_id, received_at=utcnow(), **terms))
            db.commit()
        except IntegrityError:
            db.rollback()
            raise business_error("Evenement prestataire deja lie; verifier sa correlation")
        return event.result
