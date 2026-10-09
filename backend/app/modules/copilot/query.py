from types import MappingProxyType
from typing import Literal
from datetime import date
from fastapi import HTTPException
from pydantic import AwareDatetime, field_validator, model_validator
from app.modules.base import audit, query, upstream, read_capabilities as identity
from app.modules.crm import profile, rebooking
from app.modules.copilot import planning
from app.modules.revenue import capacity
from app.modules.institutes.models import Institute
from app.modules.services.models import Service
from app.modules.crm.metrics import Fact
from app.modules.customers.repository import require_customer
from app.modules.waitlist.originals import fingerprint
from app.shared.time import utcnow, explicit_utc_instant

Name = Literal["CLIENT_READ", "CLIENT_SUMMARY", "CLIENT_REBOOKING_OPPORTUNITIES", "PLANNING_READ", "PLANNING_GAPS", "EMPLOYEE_CAPACITY"]
PROCESSES = MappingProxyType({"client-read": "CLIENT_READ", "client-summary": "CLIENT_SUMMARY",
    "client-rebooking-opportunities": "CLIENT_REBOOKING_OPPORTUNITIES", "planning-read": "PLANNING_READ",
    "planning-gaps": "PLANNING_GAPS", "employee-capacity": "EMPLOYEE_CAPACITY"})


class Selection(Fact):
    customer_id: identity.ExactId | None = None
    service_id: identity.ExactId | None = None
    day: date | None = None

    @field_validator("day", mode="before")
    @classmethod
    def explicit_day(cls, value):
        if value is not None and (type(value) is not str or len(value) != 10):
            raise ValueError("An explicit ISO calendar date is required")
        return value


class CustomerSelection(Fact):
    customer_id: identity.ExactId


class GapsSelection(Fact):
    service_id: identity.ExactId | None = None


class CapacitySelection(Fact):
    day: date


INPUTS = MappingProxyType({"CLIENT_READ": CustomerSelection, "CLIENT_SUMMARY": CustomerSelection,
    "CLIENT_REBOOKING_OPPORTUNITIES": CustomerSelection, "PLANNING_READ": query.EmptySelection,
    "PLANNING_GAPS": GapsSelection, "EMPLOYEE_CAPACITY": CapacitySelection})


class Request(query.Request):
    ui_context: Selection = Selection()


class CustomerFacts(Fact):
    customer_id: identity.ExactId
    institute_id: identity.ExactId
    display_name: str
    created_at: AwareDatetime


class Capability(Fact):
    name: Name
    level: Literal[0, 1] = 0
    permission: Literal["customer_operator", "crm_manager", "planning_operator", "capacity_manager"]
    input_schema: dict
    output_schema: dict
    application_service: str
    mutates: Literal[False] = False


REGISTRY = MappingProxyType({name: Capability(name=name, permission=permission, level=level,
    input_schema=INPUTS[name].model_json_schema(), output_schema=output.model_json_schema(),
    application_service=service) for name, permission, level, output, service in (
        ("CLIENT_READ", "customer_operator", 0, CustomerFacts, "customers.repository.require_customer"),
        ("CLIENT_SUMMARY", "crm_manager", 0, profile.SegmentProfile, "crm.profile.read"),
        ("CLIENT_REBOOKING_OPPORTUNITIES", "crm_manager", 1, rebooking.RebookingRead, "crm.rebooking.read"),
        ("PLANNING_READ", "planning_operator", 0, query.PlanningFacts, "planning.service.get_day_planning"),
        ("PLANNING_GAPS", "planning_operator", 0, planning.Gaps, "scheduling.service.availability_pool"),
        ("EMPLOYEE_CAPACITY", "capacity_manager", 0, capacity.Capacity, "revenue.capacity.read"))})


class Evidence(Fact):
    capability: Name
    institute_id: identity.ExactId
    captured_at: AwareDatetime
    read_completed_at: AwareDatetime
    result: CustomerFacts | profile.SegmentProfile | rebooking.RebookingRead | query.PlanningFacts | planning.Gaps | capacity.Capacity
    fingerprint: identity.Digest
    integrity: Literal["response_sha256_not_signature_or_retained_original"] = "response_sha256_not_signature_or_retained_original"
    complete_customer_history: Literal[False] = False

    @model_validator(mode="after")
    def coherent_capture(self):
        if self.read_completed_at < self.captured_at:
            raise ValueError("Read completion cannot precede source capture")
        if isinstance(self.result, capacity.Capacity) and (
            self.result.window.institute_id != self.institute_id or self.result.window.captured_at != self.captured_at):
            raise ValueError("Capacity source scope and capture must match evidence")
        if isinstance(self.result, planning.Gaps) and (self.result.captured_at != self.captured_at
            or any(row.institute_id != self.institute_id for row in self.result.rows)):
            raise ValueError("Availability source scope and capture must match evidence")
        return self


class Response(Fact):
    request_id: str
    status: Literal["answered", "clarification"]
    answer: str
    capability: Name | None = None
    evidence: Evidence | None = None
    actions: tuple[()] = ()
    framework: Literal["ai-swiss/base@1.5.1"] = "ai-swiss/base@1.5.1"


def read(db, principal, candidate, router=None):
    principal = query.guard(principal, principal.institute_id)
    request = Request.model_validate(candidate.model_dump(mode="json") if isinstance(candidate, Request) else candidate)
    with audit.trace(principal, "copilot_query", request.model_dump(mode="json")) as span:
        route = upstream.Route.model_validate((router or upstream.OfficialRouter()).resolve(request.message).model_dump())
        name = PROCESSES.get(route.process_id) if route.status == "routed" else None
        if name is not None and REGISTRY[name].permission in {"crm_manager", "capacity_manager"} and principal.role != "responsable_institut":
            raise HTTPException(403, "Capability requires institute manager")
        selected = {k: v for k, v in request.ui_context.model_dump().items() if v is not None}
        fields = {"CLIENT_READ": {"customer_id"}, "CLIENT_SUMMARY": {"customer_id"},
            "CLIENT_REBOOKING_OPPORTUNITIES": {"customer_id"}, "PLANNING_READ": set(),
            "PLANNING_GAPS": {"service_id"}, "EMPLOYEE_CAPACITY": {"day"}}
        if name and selected.keys() - fields[name]:
            raise HTTPException(400, "UI selection does not match the routed capability")
        required = "customer_id" if name and name.startswith("CLIENT_") else "day" if name == "EMPLOYEE_CAPACITY" else None
        if name is None or required and required not in selected:
            response = Response(request_id=span.id, status="clarification", capability=name,
                answer="Précisez la consultation et sa sélection cliente ou sa journée explicite.")
        else:
            captured = utcnow()
            if db.get(Institute, principal.institute_id) is None:
                raise HTTPException(404, "Institute not found")
            if name == "CLIENT_READ":
                row = require_customer(db, principal.institute_id, request.ui_context.customer_id)
                result = CustomerFacts(customer_id=row.id, institute_id=row.institute_id,
                    display_name=row.display_name, created_at=explicit_utc_instant(row.created_at))
                answer = "Identité enregistrée de la cliente sélectionnée."
            elif name == "CLIENT_SUMMARY":
                result = profile.read(db, principal.institute_id, request.ui_context.customer_id, _captured_at=captured)
                answer = "Profil CRM observé selon la politique enregistrée; historique complet indisponible."
                if result.unavailable_reason:
                    answer = "Segment CRM indisponible : " + result.unavailable_reason + "."
            elif name == "CLIENT_REBOOKING_OPPORTUNITIES":
                result = rebooking.read(db, principal.institute_id, request.ui_context.customer_id, _captured_at=captured)
                answer = {
                    "available": "Reprise à examiner selon la politique CRM et le dernier soin enregistré; vérifiez avec la cliente avant toute réservation.",
                    "already_booked": "Un rendez-vous actif est déjà enregistré; examinez-le avant de proposer une reprise.",
                    "not_due": "La reprise prévue par la politique CRM n'est pas encore échue.",
                    "disabled": "La règle de reprise est désactivée dans la politique CRM.",
                    "unavailable": "Opportunité de reprise indéterminée : consultez les diagnostics de source.",
                }[result.review]
            elif name == "PLANNING_READ":
                result = planning.read_day(db, principal.institute_id)
                captured = result.generated_at
                answer = "Sessions du jour fournies par le service de planning."
            elif name == "PLANNING_GAPS":
                if request.ui_context.service_id and db.get(Service, request.ui_context.service_id) is None:
                    raise HTTPException(404, "Selected service not found")
                result = planning.read_gaps(db, principal.institute_id, request.ui_context.service_id, captured)
                answer = "Fenêtres du moteur de disponibilité; horaires de travail complets et réservation non établis."
            else:
                result = capacity.read(db, principal.institute_id, request.ui_context.day)
                captured = result.window.captured_at
                answer = "Capacité enregistrée pour la journée sélectionnée; capacité physique ou réservable non établie."
            evidence = Evidence(capability=name, institute_id=principal.institute_id,
                captured_at=captured, read_completed_at=utcnow(), result=result, fingerprint="0" * 64)
            evidence = evidence.model_copy(update={"fingerprint": fingerprint(evidence.model_dump(mode="json", exclude={"fingerprint"}))})
            response = Response(request_id=span.id, status="answered", answer=answer, capability=name, evidence=evidence)
        span.result(response.status, response.capability, response.evidence.fingerprint if response.evidence else None)
        return response
