"""Explicit three-channel marketing declarations; eligibility is not delivery authority.

Separate from legacy CRM lifecycle facts, whose four communication dimensions remain
immutable. New transport declarations never infer an endpoint from a customer phone,
or a push permission from another channel. Persistence must supply the current owned
original to the evaluator; this module does not establish that a caller's head is fresh.
"""
from typing import Annotated, Literal

from pydantic import AwareDatetime, EmailStr, Field, StringConstraints, model_validator

from app.modules.crm.lifecycle import Evidence
from app.modules.crm.metrics import Fact, Identifier
from app.modules.crm.policies import Reason, Key
from app.modules.crm.segments import RegisteredCustomerFact
from app.modules.marketing.campaigns import CampaignRevision

Channel = Literal["email", "sms", "push"]
Exact = Annotated[str, StringConstraints(min_length=1, max_length=160)]


class Destination(Fact):
    channel: Channel
    # Raw addresses/tokens are excluded from repr, not from persisted explicit facts.
    email: EmailStr | None = Field(repr=False)
    phone: Annotated[str, StringConstraints(pattern=r"^\+[1-9][0-9]{1,14}$")] | None = Field(repr=False)
    push_application: Exact | None
    push_token: Annotated[str, StringConstraints(min_length=1, max_length=4096)] | None = Field(repr=False)
    evidence: Evidence

    @model_validator(mode="after")
    def exact_channel(self):
        if self.channel == "email":
            valid = self.email is not None and self.phone is self.push_application is self.push_token is None
        elif self.channel == "sms":
            valid = self.phone is not None and self.email is self.push_application is self.push_token is None
        else:
            valid = self.push_application is not None and self.push_token is not None and self.email is self.phone is None
        if not valid:
            raise ValueError("Declare exactly the destination fields for the selected channel")
        if self.push_application is not None and self.push_application.strip() != self.push_application:
            raise ValueError("An exact push application binding is required")
        if self.push_token is not None and (self.push_token.strip() != self.push_token or any(ord(c) < 32 or ord(c) == 127 for c in self.push_token)):
            raise ValueError("An exact non-control push token is required")
        return self


class Communication(Fact):
    channel: Channel
    permission: Literal["unknown", "granted", "refused"]
    permission_evidence: Evidence | None
    destination: Destination | None

    @model_validator(mode="after")
    def explicit_permission(self):
        if (self.permission == "unknown") != (self.permission_evidence is None):
            raise ValueError("Grant/refusal requires evidence; unknown remains unevidenced")
        if self.destination is not None and self.destination.channel != self.channel:
            raise ValueError("Destination must belong to its declared channel")
        return self


class Declaration(Fact):
    institute_id: Identifier
    customer_id: Identifier
    purpose: Literal["marketing"] = "marketing"
    communications: tuple[Communication, ...]

    @model_validator(mode="after")
    def complete_channels(self):
        if len(self.communications) != 3 or {c.channel for c in self.communications} != {"email", "sms", "push"}:
            raise ValueError("Declare each marketing channel exactly once, including unknowns")
        return self


class Request(Fact):
    declaration: Declaration
    previous_id: Identifier | None
    reason: Reason
    idempotency_key: Key


class Original(Request):
    id: Identifier
    actor_id: Exact
    created_at: AwareDatetime

    @model_validator(mode="after")
    def exact_original(self):
        if self.previous_id == self.id or self.id.strip() != self.id or self.previous_id is not None and self.previous_id.strip() != self.previous_id:
            raise ValueError("Exact distinct declaration identifiers required")
        if self.actor_id.strip() != self.actor_id:
            raise ValueError("An exact declaration actor is required")
        return self


class Eligibility(Fact):
    customer: RegisteredCustomerFact
    campaign: CampaignRevision
    original: Original | None
    captured_at: AwareDatetime
    reason: Literal["customer_not_retained", "campaign_not_approved", "future_campaign", "future_registration", "declaration_absent",
                    "future_declaration", "permission_unknown", "permission_refused", "destination_absent", "declared_eligible"]
    eligible_by_current_declaration: bool = Field(strict=True)
    delivery_authorized: Literal[False] = False
    external_message_sent: Literal[False] = False

    @model_validator(mode="after")
    def retained_evaluation(self):
        if self.customer.institute_id != self.campaign.institute_id:
            raise ValueError("Campaign and registered customer must share institute scope")
        if self.original is not None and (self.original.declaration.institute_id, self.original.declaration.customer_id) != (self.customer.institute_id, self.customer.customer_id):
            raise ValueError("Current declaration must belong to the registered customer")
        expected = reason(self.customer, self.campaign, self.original, self.captured_at)
        if self.reason != expected or self.eligible_by_current_declaration != (expected == "declared_eligible"):
            raise ValueError("Eligibility must match exact current declared sources")
        return self


class ObservationClock(Fact):
    captured_at: AwareDatetime


def record(identifier: str, actor: str, customer: RegisteredCustomerFact, request: Request,
           previous: Original | None, at: AwareDatetime) -> Original:
    """Append against a supplied current predecessor; database ownership/replay is separate."""
    customer = RegisteredCustomerFact.model_validate(customer.model_dump())
    request = Request.model_validate(request.model_dump())
    previous = Original.model_validate(previous.model_dump()) if previous is not None else None
    clock = ObservationClock(captured_at=at).captured_at
    scope = (customer.institute_id, customer.customer_id)
    if (request.declaration.institute_id, request.declaration.customer_id) != scope or clock < customer.created_at:
        raise ValueError("Contact declaration requires an owned registered customer and nonfuture registration")
    if previous is None:
        if request.previous_id is not None: raise ValueError("A first declaration has no predecessor")
    elif (previous.declaration.institute_id, previous.declaration.customer_id) != scope or request.previous_id != previous.id or clock < previous.created_at:
        raise ValueError("Correction requires the exact owned current predecessor and monotonic clock")
    return Original(**request.model_dump(), id=identifier, actor_id=actor, created_at=clock)


def reason(customer, campaign, original, at):
    if customer.customer_id not in campaign.content.audience.customer_ids: return "customer_not_retained"
    if campaign.state != "APPROVE": return "campaign_not_approved"
    if campaign.created_at > at: return "future_campaign"
    if customer.created_at > at: return "future_registration"
    if original is None: return "declaration_absent"
    if original.created_at > at: return "future_declaration"
    communication = next(c for c in original.declaration.communications if c.channel == campaign.content.channel)
    if communication.permission == "unknown": return "permission_unknown"
    if communication.permission == "refused": return "permission_refused"
    if communication.destination is None: return "destination_absent"
    return "declared_eligible"


def evaluate(customer: RegisteredCustomerFact, campaign: CampaignRevision, original: Original | None, at: AwareDatetime) -> Eligibility:
    customer = RegisteredCustomerFact.model_validate(customer.model_dump())
    campaign = CampaignRevision.model_validate(campaign.model_dump())
    original = Original.model_validate(original.model_dump()) if original is not None else None
    # Validate the aware observation clock before comparing source clocks.
    clock = ObservationClock(captured_at=at).captured_at
    expected = reason(customer, campaign, original, clock)
    return Eligibility(customer=customer, campaign=campaign, original=original, captured_at=clock,
                       reason=expected, eligible_by_current_declaration=expected == "declared_eligible")
