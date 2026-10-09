"""FlowPilot-owned read orchestration around the official BASE process router."""
from enum import IntEnum
import hashlib
from types import MappingProxyType
from typing import Annotated, Any, Literal, Protocol
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, AwareDatetime, Field, StringConstraints, field_validator
from app.core.permissions import can_manage_ticket
from app.modules.base import read_capabilities as identity, upstream
from app.modules.base import audit
from app.modules.crm.metrics import Fact
from app.modules.employees.models import Employee
from app.modules.institutes.models import Institute
from app.modules.services.models import Service
from app.modules.scheduling import service as scheduling, service_4b as assignment
from app.modules.planning import service as planning
from app.modules.tickets import service as tickets
from app.modules.waitlist.originals import fingerprint
from app.shared.time import utcnow, explicit_utc_instant

Name = Literal["EMPLOYEE_AVAILABILITY", "QUEUE_ASSIGNMENT_OPTIONS", "QUEUE_READ", "PLANNING_READ"]
Text = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=2000)]


class UIContext(Fact):
    employee_id: identity.ExactId | None = None
    service_id: identity.ExactId | None = None
    ticket_id: identity.ExactId | None = None


class EmployeeSelection(Fact):
    employee_id: identity.ExactId
    service_id: identity.ExactId | None = None


class TicketSelection(Fact):
    ticket_id: identity.ExactId


class EmptySelection(Fact):
    pass


class ExecutionLevel(IntEnum):
    READ = 0
    SUGGEST = 1
    PREPARE = 2
    EXECUTE = 3


class Request(Fact):
    message: Text
    ui_context: UIContext = UIContext()

    @field_validator("message")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("A nonblank message is required")
        return value


class Capability(Fact):
    name: Name
    level: Literal[0, 1]
    permission: Literal["can_manage_ticket_in_exact_signed_institute"] = "can_manage_ticket_in_exact_signed_institute"
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    application_service: str
    audit: Literal["request_id_scope_capability_and_evidence_digest_no_raw_message"] = "request_id_scope_capability_and_evidence_digest_no_raw_message"
    mutates: Literal[False] = False


PROCESS_CAPABILITIES = MappingProxyType({
    "employee-availability": "EMPLOYEE_AVAILABILITY", "queue-assignment-options": "QUEUE_ASSIGNMENT_OPTIONS",
    "queue-read": "QUEUE_READ", "planning-read": "PLANNING_READ",
})


class Proposal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    capability: Name | None


class IntentProvider(Protocol):
    def propose(self, message: str, allowed: tuple[Name, ...]) -> Proposal: ...


class Slot(Fact):
    employee_id: identity.ExactId
    institute_id: identity.ExactId
    available_from: AwareDatetime | None
    available_until: AwareDatetime | None
    reason: str
    blocking_session_id: identity.ExactId | None = None
    blocking_appointment_id: identity.ExactId | None = None
    blocking_resource_id: identity.ExactId | None = None
    blocking_absence_id: identity.ExactId | None = None


class AvailabilityFacts(Fact):
    employee_id: identity.ExactId
    institute_id: identity.ExactId
    service_id: identity.ExactId | None
    available: bool
    current_slot: Slot | None
    upcoming_slots: tuple[Slot, ...]


class Option(Fact):
    employee_id: identity.ExactId
    institute_id: identity.ExactId
    ticket_id: identity.ExactId
    assignable: bool
    available_from: AwareDatetime | None
    available_until: AwareDatetime | None
    service_duration_minutes: Annotated[int, Field(strict=True, ge=0)]
    projected_end_time: AwareDatetime | None
    reason: str
    blocking_appointment_id: identity.ExactId | None
    blocking_session_id: identity.ExactId | None


class AssignmentFacts(Fact):
    ticket_id: identity.ExactId
    options: tuple[Option, ...]


class QueueItem(Fact):
    ticket_id: identity.ExactId
    status: str
    arrival_time: AwareDatetime
    assigned_employee_id: identity.ExactId | None
    queue_position: Annotated[int, Field(strict=True, ge=1)] | None


class QueueFacts(Fact):
    items: tuple[QueueItem, ...]


class SessionFact(Fact):
    id: identity.ExactId
    employee_id: identity.ExactId
    service_id: identity.ExactId
    start_time: AwareDatetime
    planned_end_time: AwareDatetime
    status: str


class PlanningRow(Fact):
    employee_id: identity.ExactId
    employee_status: str
    sessions: tuple[SessionFact, ...]


class PlanningFacts(Fact):
    generated_at: AwareDatetime
    rows: tuple[PlanningRow, ...]


INPUTS = MappingProxyType({"EMPLOYEE_AVAILABILITY": EmployeeSelection,
    "QUEUE_ASSIGNMENT_OPTIONS": TicketSelection, "QUEUE_READ": EmptySelection, "PLANNING_READ": EmptySelection})
OUTPUTS = MappingProxyType({"EMPLOYEE_AVAILABILITY": AvailabilityFacts,
    "QUEUE_ASSIGNMENT_OPTIONS": AssignmentFacts, "QUEUE_READ": QueueFacts, "PLANNING_READ": PlanningFacts})
REGISTRY = MappingProxyType({name: Capability(name=name, level=level,
    input_schema=INPUTS[name].model_json_schema(), output_schema=OUTPUTS[name].model_json_schema(), application_service=service)
    for name, level, service in (
        ("EMPLOYEE_AVAILABILITY", 0, "scheduling.service.availability_engine"),
        ("QUEUE_ASSIGNMENT_OPTIONS", 1, "scheduling.service_4b.assignment_options_for_ticket"),
        ("QUEUE_READ", 0, "tickets.service.read_operational_queue"),
        ("PLANNING_READ", 0, "planning.service.get_day_planning"))})


class Evidence(Fact):
    institute_id: identity.ExactId
    capability: Capability
    captured_at: AwareDatetime
    read_completed_at: AwareDatetime
    result: AvailabilityFacts | AssignmentFacts | QueueFacts | PlanningFacts
    effect: Literal["read_or_suggest_only_no_mutation"] = "read_or_suggest_only_no_mutation"
    fingerprint: identity.Digest
    integrity: Literal["response_sha256_not_signature_or_retained_original"] = "response_sha256_not_signature_or_retained_original"


class Response(Fact):
    request_id: str
    status: Literal["answered", "clarification"]
    answer: str
    intent: str | None = None
    capability: Name | None = None
    evidence: Evidence | None = None
    actions: tuple[()] = ()
    framework: Literal["ai-swiss/base@1.5.1"] = "ai-swiss/base@1.5.1"


def guard(principal, institute):
    try:
        principal = identity.Principal.model_validate(principal.model_dump())
        if principal.institute_id != institute or not can_manage_ticket(principal.role):
            raise ValueError("Not authorized")
        return principal
    except (ValueError, TypeError, AttributeError) as error:
        raise HTTPException(403, "BASE query scope not authorized") from error


def _owned(db, model, identifier, institute):
    value = db.get(model, identifier)
    if value is None or value.institute_id != institute:
        raise HTTPException(404, "Selected resource not found")
    return value


def _query(db, principal, institute, candidate, router: upstream.Router | None = None,
           provider: IntentProvider | None = None, *, request_id: str):
    principal = guard(principal, institute)
    request = Request.model_validate(candidate.model_dump() if isinstance(candidate, Request) else candidate)
    # Route/prepare method context through BASE first. No DB records or UI IDs go to it.
    route = (router or upstream.OfficialRouter()).resolve(request.message)
    route = upstream.Route.model_validate(route.model_dump() if isinstance(route, upstream.Route) else route)
    if route.request_digest != hashlib.sha256(request.message.encode("utf-8")).hexdigest():
        raise HTTPException(503, "BASE routing request mismatch")
    name = PROCESS_CAPABILITIES.get(route.process_id) if route.status == "routed" and route.context_prepared else None
    if provider is not None:
        try:
            proposal = provider.propose(request.message, tuple(REGISTRY))
        except Exception:
            # Domain read path remains usable during provider outage. BASE is still required.
            proposal = None
        else:
            try:
                proposal = Proposal.model_validate(proposal.model_dump() if isinstance(proposal, Proposal) else proposal)
            except ValueError as error:
                raise HTTPException(502, "BASE intent provider returned invalid output") from error
        # Provider never authorizes a process/capability which BASE did not route.
        if proposal is not None and proposal.capability != name:
            name = None
    if name is None:
        return Response(request_id=request_id, status="clarification", answer="Précisez une consultation de disponibilité, de file ou de planning.")
    ui = request.ui_context
    selected = {k: v for k, v in ui.model_dump().items() if v is not None}
    allowed_fields = {"EMPLOYEE_AVAILABILITY": {"employee_id", "service_id"}, "QUEUE_ASSIGNMENT_OPTIONS": {"ticket_id"}, "QUEUE_READ": set(), "PLANNING_READ": set()}[name]
    if selected.keys() - allowed_fields:
        raise HTTPException(400, "UI selection does not match the routed capability")
    required = {"EMPLOYEE_AVAILABILITY": "employee_id", "QUEUE_ASSIGNMENT_OPTIONS": "ticket_id"}.get(name)
    if required and not selected.get(required):
        return Response(request_id=request_id, status="clarification", answer="Sélectionnez explicitement la collaboratrice ou le ticket concerné.", intent=route.process_id, capability=name)
    INPUTS[name].model_validate(selected)
    if db.get(Institute, institute) is None:
        raise HTTPException(404, "Institute not found")
    captured = utcnow()
    # Explicit application service dispatch. No generated SQL or dynamic callable names.
    if name == "EMPLOYEE_AVAILABILITY":
        _owned(db, Employee, ui.employee_id, institute)
        if ui.service_id:
            service = db.get(Service, ui.service_id)
            if service is None:
                raise HTTPException(404, "Selected service not found")
        result = AvailabilityFacts.model_validate(scheduling.availability_engine(db, institute, ui.employee_id, ui.service_id, now=captured).to_dict())
        answer = "Disponibilité calculée par le moteur métier pour la collaboratrice sélectionnée."
    elif name == "QUEUE_ASSIGNMENT_OPTIONS":
        try:
            options = assignment.assignment_options_for_ticket(db, institute, ui.ticket_id, now=captured)
        except ValueError as error:
            raise HTTPException(404, "Selected ticket not found") from error
        result = AssignmentFacts(ticket_id=ui.ticket_id, options=tuple(Option.model_validate({k: v for k, v in item.to_dict().items() if k != "employee_name"}) for item in options))
        answer = "Options d'affectation calculées par le moteur métier; aucune affectation effectuée."
    elif name == "QUEUE_READ":
        result = QueueFacts(items=tuple(QueueItem.model_validate(item) for item in tickets.read_operational_queue(db, institute)))
        answer = f"{len(result.items)} ticket(s) dans le flux opérationnel."
    else:
        value = planning.get_day_planning(db, institute)
        result = PlanningFacts(generated_at=explicit_utc_instant(value.generated_at), rows=tuple(
            PlanningRow(employee_id=row.employee_id, employee_status=row.employee_status, sessions=tuple(
                SessionFact(id=s.id, employee_id=s.employee_id, service_id=s.service_id,
                            start_time=explicit_utc_instant(s.start_time), planned_end_time=explicit_utc_instant(s.planned_end_time), status=s.status)
                for s in row.sessions)) for row in value.rows))
        captured = result.generated_at
        answer = "Sessions du jour fournies par le service de planning."
    body = dict(institute_id=institute, capability=REGISTRY[name], captured_at=captured,
                read_completed_at=utcnow(), result=result)
    evidence = Evidence(**body, fingerprint="0" * 64)
    evidence = evidence.model_copy(update={"fingerprint": fingerprint(evidence.model_dump(mode="json", exclude={"fingerprint"}))})
    return Response(request_id=request_id, status="answered", answer=answer, intent=route.process_id, capability=name, evidence=evidence)


def query(db, principal, institute, candidate, router: upstream.Router | None = None,
          provider: IntentProvider | None = None):
    # Signed scope is validated before any framework call or application dispatch.
    principal = guard(principal, institute)
    request = Request.model_validate(candidate.model_dump() if isinstance(candidate, Request) else candidate)
    with audit.trace(principal, "query", request.model_dump(mode="json")) as span:
        response = _query(db, principal, institute, request, router, provider, request_id=span.id)
        span.result(response.status, response.capability, response.evidence.fingerprint if response.evidence else None)
        return response
