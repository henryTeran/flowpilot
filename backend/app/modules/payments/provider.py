"""Provider boundary: explicit units, scoped replay intent, no inferred settlement."""
from dataclasses import dataclass, field
from decimal import Decimal, localcontext
from enum import Enum
from types import MappingProxyType
from typing import Mapping, Protocol, runtime_checkable


class ProviderStatus(str, Enum):
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"
    PENDING = "pending"
    FAILED = "failed"


def identifier(value: str, limit: int):
    if not isinstance(value, str) or not value.strip() or value != value.strip() or len(value) > limit:
        raise ValueError("Explicit bounded identifier required")


@dataclass(frozen=True)
class PaymentAmount:
    amount: Decimal
    currency: str

    def __post_init__(self):
        if self.currency not in {"CHF", "EUR"}:
            raise ValueError("Explicit supported currency required")
        if not isinstance(self.amount, Decimal) or not self.amount.is_finite() or not Decimal("0") < self.amount <= Decimal("99999999.99"):
            raise ValueError("Positive finite decimal amount required")
        with localcontext() as context:
            context.prec = 28
            normalized = self.amount.quantize(Decimal("0.01"))
        if self.amount != normalized:
            raise ValueError("Payment amount must have whole cents")
        object.__setattr__(self, "amount", normalized)


@dataclass(frozen=True)
class PaymentRequest:
    institute_id: str
    ticket_id: str
    value: PaymentAmount
    idempotency_key: str
    actor_id: str

    def __post_init__(self):
        for value, limit in ((self.institute_id, 80), (self.ticket_id, 80), (self.idempotency_key, 120), (self.actor_id, 160)):
            identifier(value, limit)
        if not isinstance(self.value, PaymentAmount):
            raise ValueError("Typed amount required")


@dataclass(frozen=True)
class ProviderResult:
    provider_payment_id: str
    status: ProviderStatus
    value: PaymentAmount

    def __post_init__(self):
        identifier(self.provider_payment_id, 240)
        if not isinstance(self.status, ProviderStatus) or not isinstance(self.value, PaymentAmount):
            raise ValueError("Typed provider status and amount required")


@dataclass(frozen=True)
class RawWebhook:
    body: bytes = field(repr=False)
    headers: Mapping[str, str] = field(repr=False)

    def __post_init__(self):
        if not isinstance(self.body, bytes) or not isinstance(self.headers, Mapping) or any(
            not isinstance(key, str) or not isinstance(value, str) for key, value in self.headers.items()
        ):
            raise ValueError("Raw bytes and string headers required")
        object.__setattr__(self, "headers", MappingProxyType(dict(self.headers)))


@dataclass(frozen=True)
class VerifiedWebhook:
    """Adapter output after authenticating raw bytes against its configured account.

    Never accept this type or a client supplied verified flag at a public endpoint.
    Resolve tenant/ticket through stored provider references in the payment domain.
    """
    event_id: str
    result: ProviderResult

    def __post_init__(self):
        identifier(self.event_id, 240)
        if not isinstance(self.result, ProviderResult):
            raise ValueError("Typed provider result required")


@runtime_checkable
class PaymentProvider(Protocol):
    """Adapters perform I/O; the domain persists intent and applies facts exactly once.

    Timeout is an unknown outcome. Retry the original scoped key; never create a
    new payment to infer failure. Results require request/reference/unit validation
    before checkout closure. Internal cashier confirmation is a separate fact.
    """
    def authorize(self, request: PaymentRequest) -> ProviderResult: ...
    def capture(self, request: PaymentRequest, provider_payment_id: str) -> ProviderResult: ...
    def refund(self, request: PaymentRequest, provider_payment_id: str) -> ProviderResult: ...
    def cancel(self, request: PaymentRequest, provider_payment_id: str) -> ProviderResult: ...
    def webhook(self, event: RawWebhook) -> VerifiedWebhook: ...
