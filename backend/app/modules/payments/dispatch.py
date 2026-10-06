"""Trusted account-bound authorization dispatch, with no transaction across I/O."""
from dataclasses import dataclass, field
from sqlalchemy import select
from app.modules.payments.provider import PaymentProvider, ProviderResult, ProviderStatus, PaymentAmount, identifier
from app.modules.payments.models import PaymentIntent, PaymentOutcome
from app.modules.payments.executions import seal_authorization
from app.modules.payments.outcomes import record_authorization_outcome
from app.shared.exceptions import business_error, not_found


@dataclass(frozen=True)
class ProviderBinding:
    """Server configuration only; never deserialize an adapter from a request."""
    institute_id: str
    provider: str
    account_id: str
    adapter: PaymentProvider = field(repr=False)

    def __post_init__(self):
        for value in (self.institute_id, self.provider, self.account_id):
            identifier(value, 80)
        if not isinstance(self.adapter, PaymentProvider):
            raise ValueError("Complete payment provider adapter required")


def dispatch_authorization(session_factory, institute_id, intent_id, binding: ProviderBinding):
    """Own short sessions so callbacks never inherit a business lock/transaction.

    Adapter must authenticate responses and guarantee idempotence of the original
    request key, including concurrent retry. Transport/write failure stays unknown.
    This function supplies neither default adapter nor public dispatch endpoint.
    """
    if not isinstance(binding, ProviderBinding) or binding.institute_id != institute_id:
        raise business_error("Configuration prestataire de cet institut requise")
    with session_factory() as db:
        intent = db.scalar(select(PaymentIntent).where(PaymentIntent.id == intent_id,
                                                      PaymentIntent.institute_id == institute_id))
        if intent is None:
            raise not_found("Intention de paiement introuvable")
        if (intent.provider, intent.account_id, intent.kind) != (binding.provider, binding.account_id, "authorize"):
            raise business_error("Compte prestataire incompatible avec la demande initiale")
        request = seal_authorization(db, institute_id, intent_id)
        terminal = db.scalar(select(PaymentOutcome).where(PaymentOutcome.intent_id == intent_id,
                                                          PaymentOutcome.status != "pending"))
        if terminal is not None:
            return ProviderResult(terminal.provider_payment_id, ProviderStatus(terminal.status),
                                  PaymentAmount(terminal.amount, terminal.currency))
    # The persisted seal remains active; the SQL session and its locks are closed.
    result = binding.adapter.authorize(request)
    with session_factory() as db:
        record_authorization_outcome(db, institute_id, intent_id, binding.provider, binding.account_id, result)
    return result



def dispatch_parent_operation(session_factory, institute_id, intent_id, binding: ProviderBinding):
    from app.modules.payments.models import ParentOperationOutcome
    from app.modules.payments.executions import seal_parent_operation
    from app.modules.payments.outcomes import record_parent_outcome
    if not isinstance(binding, ProviderBinding) or binding.institute_id != institute_id:
        raise business_error("Configuration prestataire de cet institut requise")
    with session_factory() as db:
        intent = db.scalar(select(PaymentIntent).where(PaymentIntent.id == intent_id,
                                                      PaymentIntent.institute_id == institute_id))
        if intent is None:
            raise not_found("Intention de paiement introuvable")
        if intent.kind not in {"capture", "cancel"} or (intent.provider, intent.account_id) != (binding.provider, binding.account_id):
            raise business_error("Compte ou operation incompatible")
        kind, reference = intent.kind, intent.provider_payment_id
        request = seal_parent_operation(db, institute_id, intent_id)
        terminal = db.scalar(select(ParentOperationOutcome).where(ParentOperationOutcome.intent_id == intent_id,
                                                                  ParentOperationOutcome.status != "pending"))
        if terminal is not None:
            return ProviderResult(terminal.provider_payment_id, ProviderStatus(terminal.status),
                                  PaymentAmount(terminal.amount, terminal.currency))
    method = binding.adapter.capture if kind == "capture" else binding.adapter.cancel
    result = method(request, reference)
    with session_factory() as db:
        record_parent_outcome(db, institute_id, intent_id, binding.provider, binding.account_id, result)
    return result
