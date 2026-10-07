"""Typed transport boundary, without I/O, credentials or database authority.

The dispatcher must persist intent before I/O, supply current owned eligibility,
resolve an enabled account from trusted configuration, and retain uncertain outcomes.
A timeout never permits a new operation key. Provider acceptance is not delivery.
"""
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Annotated, Literal, Protocol, runtime_checkable

from pydantic import AwareDatetime, Field, StringConstraints, model_validator
from app.modules.crm.metrics import Fact, Identifier
from app.modules.marketing import contacts

Exact = Annotated[str, StringConstraints(min_length=1, max_length=160)]
OperationKey = Annotated[str, StringConstraints(min_length=1, max_length=120)]
Fingerprint = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]


class Account(Fact):
    institute_id: Identifier
    provider: Exact
    account_id: Exact
    channel: contacts.Channel
    sender_id: Exact
    mode: Literal["live", "test"]
    push_application: Exact | None

    @model_validator(mode="after")
    def binding(self):
        if any(v != v.strip() or any(ord(c) < 32 or ord(c) == 127 for c in v)
               for v in (self.provider, self.account_id, self.sender_id) + ((self.push_application,) if self.push_application is not None else ())):
            raise ValueError("Exact non-control configured account identifiers required")
        if (self.channel == "push") != (self.push_application is not None):
            raise ValueError("Push requires an explicit configured application binding")
        return self


class Submission(Fact):
    """Stored transport terms; possession does not prove current dispatch authority."""
    account: Account
    eligibility: contacts.Eligibility = Field(repr=False)
    actor_id: Exact
    idempotency_key: OperationKey

    @model_validator(mode="after")
    def coherent_sources(self):
        # Revalidate even typed model_copy/model_construct values from internal callers.
        a = Account.model_validate(self.account.model_dump())
        e = contacts.Eligibility.model_validate(self.eligibility.model_dump())
        if not e.eligible_by_current_declaration or e.original is None:
            raise ValueError("Explicit eligible approved recipient sources required")
        if a.institute_id != e.customer.institute_id or a.channel != e.campaign.content.channel:
            raise ValueError("Configured account must match owned campaign channel")
        destination = next(c.destination for c in e.original.declaration.communications if c.channel == a.channel)
        if a.channel == "push" and destination.push_application != a.push_application:
            raise ValueError("Declared device must match configured push application")
        if any(v != v.strip() or any(ord(c) < 32 or ord(c) == 127 for c in v) for v in (self.actor_id, self.idempotency_key)):
            raise ValueError("Exact actor and original operation key required")
        return self


def fingerprint(request: Submission) -> str:
    request = Submission.model_validate(request.model_dump())
    def canonical(value):
        if isinstance(value, datetime):
            return value.astimezone(timezone.utc).isoformat()
        if isinstance(value, dict):
            return {k: canonical(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [canonical(v) for v in value]
        return value
    return sha256(json.dumps(canonical(request.model_dump()), sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


class Result(Fact):
    account: Account
    idempotency_key: OperationKey
    request_fingerprint: Fingerprint
    status: Literal["accepted", "rejected", "unknown"]
    provider_message_id: Annotated[str, StringConstraints(min_length=1, max_length=240)] | None
    observed_at: AwareDatetime
    delivery_confirmed: bool = Field(strict=True, default=False)

    @model_validator(mode="after")
    def submission_outcome(self):
        Account.model_validate(self.account.model_dump())
        if self.delivery_confirmed:
            raise ValueError("Submission acceptance cannot confirm recipient delivery")
        if self.status == "accepted" and self.provider_message_id is None:
            raise ValueError("Provider acceptance requires its explicit message reference")
        for value in (self.idempotency_key, self.provider_message_id):
            if value is not None and (value != value.strip() or any(ord(c) < 32 or ord(c) == 127 for c in value)):
                raise ValueError("Exact operation/provider references required")
        return self


def validate_result(request: Submission, result: Result) -> Result:
    request = Submission.model_validate(request.model_dump())
    result = Result.model_validate(result.model_dump())
    if result.account != request.account or result.idempotency_key != request.idempotency_key or result.request_fingerprint != fingerprint(request):
        raise ValueError("Provider outcome must match exact persisted account and operation terms")
    if result.observed_at < request.eligibility.captured_at:
        raise ValueError("Provider observation cannot precede supplied recipient check")
    return result


@runtime_checkable
class MarketingProvider(Protocol):
    """Adapters submit or reconcile one stored key under a configured account.

    Both operations must preserve exact content/destination and scoped key. An
    adapter lacking idempotent submission/reconciliation cannot support automatic
    retry after uncertain I/O. Authentication/webhook and delivery-event evidence
    belong to separate verified boundaries, never a client-supplied Result.
    """
    def submit(self, request: Submission) -> Result: ...
    def reconcile(self, request: Submission) -> Result: ...
