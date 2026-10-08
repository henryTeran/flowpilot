"""Closed read/suggest registry. No dynamic tools, SQL, mutations or LLM truth."""
from datetime import timezone
from types import MappingProxyType
from typing import Annotated, Any, Literal
from pydantic import AwareDatetime, StringConstraints, Field, TypeAdapter, model_validator, BaseModel, ConfigDict
from app.core.permissions import UserRole
from app.modules.crm.metrics import Fact
from app.modules.waitlist import lifecycle, sources as matching
from app.modules.optimizer import sources as optimizer
from app.shared.time import utcnow
from app.shared.exceptions import business_error
from fastapi import HTTPException

ExactId = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=80)]
Actor = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=160)]
Digest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
Name = Literal["WAITLIST_READ", "WAITLIST_MATCH", "PLANNING_OPTIMIZATION"]


class Principal(Fact):
    actor_id: Actor
    institute_id: ExactId
    role: UserRole

    @model_validator(mode="after")
    def exact_scope(self):
        if any(value != value.strip() or any(ord(c) < 32 for c in value) for value in (self.actor_id, self.institute_id)):
            raise ValueError("An exact signed actor/institute is required")
        return self


def signed_principal(user, institute):
    """Only call with server-decoded JWT claims, never an HTTP body/provider value."""
    try:
        principal = Principal(actor_id=user.get("sub"), institute_id=user.get("institute_id"), role=user.get("role"))
        if principal.institute_id != institute:
            raise ValueError("Tenant mismatch")
        return principal
    except (ValueError, TypeError, AttributeError) as error:
        raise HTTPException(403, "BASE principal requires verified signed scope") from error


class ReadArguments(Fact):
    root_id: ExactId


class MatchArguments(ReadArguments):
    expected_event_id: ExactId
    expected_event_fingerprint: Digest
    horizon_end: matching.Horizon
    policy: matching.Policy


class InvocationModel(BaseModel):
    # Fact's wildcard before-validator is intentionally excluded from the literal
    # discriminator. Nested argument facts retain their aware-time/source guards.
    model_config = ConfigDict(extra="forbid", frozen=True)


class ReadInvocation(InvocationModel):
    capability: Literal["WAITLIST_READ"]
    arguments: ReadArguments


class MatchInvocation(InvocationModel):
    capability: Literal["WAITLIST_MATCH"]
    arguments: MatchArguments


class OptimizeInvocation(InvocationModel):
    capability: Literal["PLANNING_OPTIMIZATION"]
    arguments: optimizer.Request


Invocation = Annotated[ReadInvocation | MatchInvocation | OptimizeInvocation, Field(discriminator="capability")]
INVOCATIONS = TypeAdapter(Invocation)


class Capability(Fact):
    name: Name
    level: Literal[0, 1]
    roles: tuple[Literal["responsable_institut"], ...]
    context: Literal["exact_signed_institute_and_explicit_selected_references"] = "exact_signed_institute_and_explicit_selected_references"
    application_service: Literal["waitlist.lifecycle.read_state", "waitlist.sources.read", "optimizer.sources.read"]
    mutates: Literal[False] = False
    external_execution: Literal[False] = False
    approval: Literal["not_required_for_read_or_suggest_only"] = "not_required_for_read_or_suggest_only"


REGISTRY = MappingProxyType({
    "WAITLIST_READ": Capability(name="WAITLIST_READ", level=0, roles=("responsable_institut",), application_service="waitlist.lifecycle.read_state"),
    "WAITLIST_MATCH": Capability(name="WAITLIST_MATCH", level=1, roles=("responsable_institut",), application_service="waitlist.sources.read"),
    "PLANNING_OPTIMIZATION": Capability(name="PLANNING_OPTIMIZATION", level=1, roles=("responsable_institut",), application_service="optimizer.sources.read"),
})


def authorize(principal: Principal, institute: str, capability: Name):
    try:
        principal = Principal.model_validate(principal.model_dump())
        descriptor = REGISTRY[capability]
        if principal.institute_id != institute or principal.role.value not in descriptor.roles:
            raise ValueError("Capability denied")
        return principal, descriptor
    except (ValueError, TypeError, AttributeError, KeyError) as error:
        raise HTTPException(403, "BASE capability not authorized") from error


def capabilities(principal: Principal, institute: str):
    """Discovery exposes only registered capabilities permitted in exact scope."""
    principal = Principal.model_validate(principal.model_dump())
    if principal.institute_id != institute:
        raise HTTPException(403, "BASE institute not authorized")
    return tuple(c for c in REGISTRY.values() if principal.role.value in c.roles)


class Context(Fact):
    principal: Principal
    capability: Capability
    selected_arguments: dict[str, Any]
    basis: Literal["authorized_selection_not_captured_business_facts"] = "authorized_selection_not_captured_business_facts"


def resolve(principal: Principal, institute: str, candidate):
    """Validate a structured candidate; natural-language resolution is separate."""
    try:
        request = INVOCATIONS.validate_python(candidate.model_dump() if isinstance(candidate, BaseModel) else candidate)
    except (ValueError, TypeError) as error:
        raise business_error("BASE requires an explicit registered structured selection") from error
    principal, descriptor = authorize(principal, institute, request.capability)
    context = Context(principal=principal, capability=descriptor, selected_arguments=request.arguments.model_dump(mode="json"))
    return context, request


class Evidence(Fact):
    context: Context
    read_completed_at: AwareDatetime
    result: lifecycle.State | matching.Read | optimizer.Read
    effect: Literal["read_or_suggestion_only_no_booking_contact_or_external_execution"] = "read_or_suggestion_only_no_booking_contact_or_external_execution"


def invoke(db, principal: Principal, institute: str, candidate):
    context, request = resolve(principal, institute, candidate)
    # Explicit service dispatch only; business/source guards stay in the existing
    # service. Never interpret a path, callable name or generated SQL as a tool.
    if isinstance(request, ReadInvocation):
        result = lifecycle.read_state(db, institute, request.arguments.root_id)
    elif isinstance(request, MatchInvocation):
        a = request.arguments
        result = matching.read(db, institute, a.root_id, a.expected_event_id, a.expected_event_fingerprint, a.horizon_end, a.policy)
    else:
        result = optimizer.read(db, institute, request.arguments)
    # Completion time labels this wrapper read, not a shared business capture.
    # Captured source clocks are preserved in the unchanged service result.
    return Evidence(context=context, read_completed_at=utcnow().astimezone(timezone.utc), result=result)
