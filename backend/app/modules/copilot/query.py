from types import MappingProxyType
from typing import Literal
from datetime import date, datetime
from fastapi import HTTPException
from pydantic import AwareDatetime, ConfigDict, TypeAdapter, field_validator, model_validator
from app.modules.base import audit, query, upstream, read_capabilities as identity
from app.modules.crm import profile, rebooking
from app.modules.copilot import planning, losses, opportunities
from app.modules.revenue import capacity, sources as revenue_sources, billing, slot_opportunities
from app.modules.workforce import conflicts
from app.modules.resources import conflicts as resource_conflicts
from app.modules.inventory import outlook
from app.modules.inventory.outlook_schemas import ForecastScenario, OutlookRead
from app.modules.institutes.models import Institute
from app.modules.services.models import Service
from app.modules.crm.metrics import Fact
from app.modules.customers.repository import require_customer
from app.modules.waitlist.originals import fingerprint
from app.shared.time import utcnow, explicit_utc_instant

Name = Literal["CLIENT_READ", "CLIENT_SUMMARY", "CLIENT_REBOOKING_OPPORTUNITIES", "PLANNING_READ", "PLANNING_GAPS", "EMPLOYEE_CAPACITY", "PLANNING_CONFLICTS", "REVENUE_SUMMARY", "REVENUE_OPPORTUNITIES", "REVENUE_LOSS_ANALYSIS", "STOCK_READ", "STOCK_FORECAST"]
PROCESSES = MappingProxyType({"client-read": "CLIENT_READ", "client-summary": "CLIENT_SUMMARY",
    "client-rebooking-opportunities": "CLIENT_REBOOKING_OPPORTUNITIES", "planning-read": "PLANNING_READ",
    "planning-gaps": "PLANNING_GAPS", "employee-capacity": "EMPLOYEE_CAPACITY", "planning-conflicts": "PLANNING_CONFLICTS", "revenue-summary": "REVENUE_SUMMARY", "revenue-opportunities": "REVENUE_OPPORTUNITIES", "revenue-loss-analysis": "REVENUE_LOSS_ANALYSIS", "stock-read": "STOCK_READ", "stock-forecast": "STOCK_FORECAST"})


class Scenario(ForecastScenario):
    @field_validator("starts_at", "ends_at", mode="before")
    @classmethod
    def explicit_instants(cls, value):
        if not isinstance(value, (str, datetime)) or isinstance(value, str) and "T" not in value:
            raise ValueError("Explicit aware ISO scenario instants required")
        return value


class Selection(Fact):
    customer_id: identity.ExactId | None = None
    service_id: identity.ExactId | None = None
    employee_id: identity.ExactId | None = None
    resource_id: identity.ExactId | None = None
    day: date | None = None
    start: AwareDatetime | None = None
    end: AwareDatetime | None = None
    horizon_end: AwareDatetime | None = None
    scenario: Scenario | None = None
    opportunity_source: Literal["capacity", "rebooking", "closures"] | None = None

    @field_validator("horizon_end", mode="before")
    @classmethod
    def explicit_horizon(cls, value):
        if value is not None and (not isinstance(value, (str, datetime)) or isinstance(value, str) and "T" not in value):
            raise ValueError("An explicit aware ISO horizon is required")
        return value

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


class BillingSelection(Fact):
    start: AwareDatetime
    end: AwareDatetime


class OpportunitySelection(Fact):
    model_config = ConfigDict(extra="forbid", frozen=True, json_schema_extra={"oneOf": [
        {"required": ["service_id", "horizon_end"], "properties": {
            "opportunity_source": {"const": "capacity"}, "service_id": {"type": "string"}, "horizon_end": {"type": "string"}, "start": {"type": "null"}, "end": {"type": "null"}}},
        {"required": ["opportunity_source"], "properties": {
            "opportunity_source": {"const": "rebooking"}, "service_id": {"type": "null"}, "horizon_end": {"type": "null"}, "start": {"type": "null"}, "end": {"type": "null"}}},
        {"required": ["opportunity_source", "start", "end"], "properties": {
            "opportunity_source": {"const": "closures"}, "service_id": {"type": "null"}, "horizon_end": {"type": "null"}, "start": {"type": "string"}, "end": {"type": "string"}}},
    ]})
    opportunity_source: Literal["capacity", "rebooking", "closures"] = "capacity"
    service_id: identity.ExactId | None = None
    horizon_end: AwareDatetime | None = None
    start: AwareDatetime | None = None
    end: AwareDatetime | None = None

    @model_validator(mode="after")
    def source_selection(self):
        if self.opportunity_source == "capacity" and (self.service_id is None or self.horizon_end is None):
            raise ValueError("Capacity requires an explicit service and horizon")
        if self.opportunity_source == "rebooking" and (self.service_id is not None or self.horizon_end is not None):
            raise ValueError("Rebooking does not accept capacity selections")
        if self.opportunity_source != "closures" and (self.start is not None or self.end is not None):
            raise ValueError("Only closure follow-up accepts an observed period")
        if self.opportunity_source == "closures" and (self.start is None or self.end is None or self.service_id is not None or self.horizon_end is not None):
            raise ValueError("Closure follow-up requires only an explicit period")
        return self


class ForecastSelection(Fact):
    scenario: Scenario


class ConflictsSelection(CapacitySelection):
    model_config = ConfigDict(extra="forbid", frozen=True, json_schema_extra={"oneOf": [
        {"required": ["employee_id"], "properties": {"employee_id": {"type": "string"}, "resource_id": {"type": "null"}}},
        {"required": ["resource_id"], "properties": {"resource_id": {"type": "string"}, "employee_id": {"type": "null"}}},
    ]})
    employee_id: identity.ExactId | None = None
    resource_id: identity.ExactId | None = None

    @model_validator(mode="after")
    def one_target(self):
        if (self.employee_id is None) == (self.resource_id is None):
            raise ValueError("Select exactly one employee or resource")
        return self


INPUTS = MappingProxyType({"CLIENT_READ": CustomerSelection, "CLIENT_SUMMARY": CustomerSelection,
    "CLIENT_REBOOKING_OPPORTUNITIES": CustomerSelection, "PLANNING_READ": query.EmptySelection,
    "PLANNING_GAPS": GapsSelection, "EMPLOYEE_CAPACITY": CapacitySelection, "PLANNING_CONFLICTS": ConflictsSelection,
    "REVENUE_SUMMARY": BillingSelection, "REVENUE_OPPORTUNITIES": OpportunitySelection, "REVENUE_LOSS_ANALYSIS": BillingSelection,
    "STOCK_READ": query.EmptySelection, "STOCK_FORECAST": ForecastSelection})


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
    permission: Literal["customer_operator", "crm_manager", "planning_operator", "capacity_manager", "inventory_operator"]
    input_schema: dict
    output_schema: dict
    application_service: str
    audit: Literal["signed_scope_interaction_id_and_source_digest_no_raw_message"] = "signed_scope_interaction_id_and_source_digest_no_raw_message"
    mutates: Literal[False] = False


REGISTRY = MappingProxyType({name: Capability(name=name, permission=permission, level=level,
    input_schema=INPUTS[name].model_json_schema(), output_schema=TypeAdapter(conflicts.Read | resource_conflicts.Read).json_schema() if name == "PLANNING_CONFLICTS" else TypeAdapter(slot_opportunities.Read | opportunities.Returns | opportunities.FollowUps).json_schema() if name == "REVENUE_OPPORTUNITIES" else output.model_json_schema(),
    application_service=service) for name, permission, level, output, service in (
        ("CLIENT_READ", "customer_operator", 0, CustomerFacts, "customers.repository.require_customer"),
        ("CLIENT_SUMMARY", "crm_manager", 0, profile.SegmentProfile, "crm.profile.read"),
        ("CLIENT_REBOOKING_OPPORTUNITIES", "crm_manager", 1, rebooking.RebookingRead, "crm.rebooking.read"),
        ("PLANNING_READ", "planning_operator", 0, query.PlanningFacts, "planning.service.get_day_planning"),
        ("PLANNING_GAPS", "planning_operator", 0, planning.Gaps, "scheduling.service.availability_pool"),
        ("EMPLOYEE_CAPACITY", "capacity_manager", 0, capacity.Capacity, "revenue.capacity.read"),
        ("PLANNING_CONFLICTS", "capacity_manager", 0, conflicts.Read, "workforce.conflicts.read/resources.conflicts.read"),
        ("REVENUE_SUMMARY", "capacity_manager", 0, billing.Billing, "revenue.sources.read"),
        ("REVENUE_OPPORTUNITIES", "capacity_manager", 1, slot_opportunities.Read, "revenue.slot_opportunities.read/copilot.opportunities.read_returns/copilot.opportunities.read_follow_ups"),
        ("REVENUE_LOSS_ANALYSIS", "capacity_manager", 0, losses.Read, "copilot.losses.read/revenue.closures/revenue.walk_in_cancellations"),
        ("STOCK_READ", "inventory_operator", 0, OutlookRead, "inventory.outlook.read"),
        ("STOCK_FORECAST", "inventory_operator", 1, OutlookRead, "inventory.outlook.read/explicit_scenario"))})


OUTPUT_TYPES = MappingProxyType({
    "CLIENT_READ": CustomerFacts, "CLIENT_SUMMARY": profile.SegmentProfile,
    "CLIENT_REBOOKING_OPPORTUNITIES": rebooking.RebookingRead, "PLANNING_READ": query.PlanningFacts,
    "PLANNING_GAPS": planning.Gaps, "EMPLOYEE_CAPACITY": capacity.Capacity,
    "PLANNING_CONFLICTS": (conflicts.Read, resource_conflicts.Read), "REVENUE_SUMMARY": billing.Billing,
    "REVENUE_OPPORTUNITIES": (slot_opportunities.Read, opportunities.Returns, opportunities.FollowUps), "REVENUE_LOSS_ANALYSIS": losses.Read,
    "STOCK_READ": OutlookRead, "STOCK_FORECAST": OutlookRead,
})


class Evidence(Fact):
    capability: Name
    institute_id: identity.ExactId
    captured_at: AwareDatetime
    read_completed_at: AwareDatetime
    result: CustomerFacts | profile.SegmentProfile | rebooking.RebookingRead | query.PlanningFacts | planning.Gaps | capacity.Capacity | conflicts.Read | resource_conflicts.Read | billing.Billing | slot_opportunities.Read | opportunities.Returns | opportunities.FollowUps | losses.Read | OutlookRead
    fingerprint: identity.Digest
    integrity: Literal["response_sha256_not_signature_or_retained_original"] = "response_sha256_not_signature_or_retained_original"
    complete_customer_history: Literal[False] = False

    @model_validator(mode="after")
    def coherent_capture(self):
        if not isinstance(self.result, OUTPUT_TYPES[self.capability]):
            raise ValueError("Evidence result must match the registered capability")
        if isinstance(self.result, CustomerFacts) and self.result.institute_id != self.institute_id:
            raise ValueError("Customer source scope must match evidence")
        if isinstance(self.result, (profile.SegmentProfile, rebooking.RebookingRead)) and (
            self.result.institute_id != self.institute_id or self.result.captured_at != self.captured_at):
            raise ValueError("CRM source scope and capture must match evidence")
        if isinstance(self.result, query.PlanningFacts) and self.result.generated_at != self.captured_at:
            raise ValueError("Planning source capture must match evidence")
        if self.read_completed_at < self.captured_at:
            raise ValueError("Read completion cannot precede source capture")
        if isinstance(self.result, OutlookRead) and (self.result.institute_id != self.institute_id
            or explicit_utc_instant(self.result.generated_at) != self.captured_at):
            raise ValueError("Inventory source scope and capture must match evidence")
        if isinstance(self.result, OutlookRead) and self.result.source != (
            "recorded_stock" if self.capability == "STOCK_READ" else "explicit_service_volume_scenario"):
            raise ValueError("Stock source must match read or forecast capability")
        if isinstance(self.result, (capacity.Capacity, billing.Billing)) and (
            self.result.window.institute_id != self.institute_id or self.result.window.captured_at != self.captured_at):
            raise ValueError("Capacity source scope and capture must match evidence")
        if isinstance(self.result, planning.Gaps) and (self.result.captured_at != self.captured_at
            or any(row.institute_id != self.institute_id for row in self.result.rows)):
            raise ValueError("Availability source scope and capture must match evidence")
        if isinstance(self.result, (conflicts.Read, resource_conflicts.Read, slot_opportunities.Read, opportunities.Returns, opportunities.FollowUps, losses.Read)) and (
            self.result.institute_id != self.institute_id or self.result.captured_at != self.captured_at):
            raise ValueError("Conflict source scope and capture must match evidence")
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
            "PLANNING_GAPS": {"service_id"}, "EMPLOYEE_CAPACITY": {"day"}, "PLANNING_CONFLICTS": {"employee_id", "resource_id", "day"},
            "REVENUE_SUMMARY": {"start", "end"}, "REVENUE_OPPORTUNITIES": {"service_id", "horizon_end", "opportunity_source"}, "REVENUE_LOSS_ANALYSIS": {"start", "end"},
            "STOCK_READ": set(), "STOCK_FORECAST": {"scenario"}}
        opportunity_fields = {"capacity": {"service_id", "horizon_end"}, "rebooking": set(), "closures": {"start", "end"}}
        if name == "REVENUE_OPPORTUNITIES":
            fields[name] = {"opportunity_source"} | opportunity_fields[request.ui_context.opportunity_source or "capacity"]
        if name and selected.keys() - fields[name]:
            raise HTTPException(400, "UI selection does not match the routed capability")
        if name == "PLANNING_CONFLICTS" and selected.get("employee_id") and selected.get("resource_id"):
            raise HTTPException(400, "Select exactly one employee or resource")
        required = {"customer_id"} if name and name.startswith("CLIENT_") else {"day"} if name in {"EMPLOYEE_CAPACITY", "PLANNING_CONFLICTS"} else set()
        if name in {"REVENUE_SUMMARY", "REVENUE_LOSS_ANALYSIS"}:
            required = {"start", "end"}
        elif name == "REVENUE_OPPORTUNITIES":
            required = opportunity_fields[request.ui_context.opportunity_source or "capacity"]
        elif name == "STOCK_FORECAST":
            required = {"scenario"}
        missing_target = name == "PLANNING_CONFLICTS" and not (selected.get("employee_id") or selected.get("resource_id"))
        if name is None or required - selected.keys() or missing_target:
            response = Response(request_id=span.id, status="clarification", capability=name,
                answer="Précisez la consultation et les sélections requises : cliente, cible, journée ou période explicite.")
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
            elif name == "PLANNING_CONFLICTS":
                if request.ui_context.resource_id:
                    result = resource_conflicts.read(db, principal.institute_id, request.ui_context.resource_id, request.ui_context.day)
                    answer = f"{result.overlap_count} chevauchement(s) de réservations enregistrées pour la ressource sélectionnée."
                    if result.invalid_source_count or result.overdue_unreleased_source_count or result.resource_status != "active":
                        answer += " Sources invalides, réservations dépassées ou ressource indisponible : capacité non établie."
                else:
                    result = conflicts.read(db, principal.institute_id, request.ui_context.employee_id, request.ui_context.day)
                    answer = f"{result.overlap_count} chevauchement(s) d'engagements enregistrés pour la collaboratrice; conflits de ressources non couverts."
                    if result.invalid_source_count or result.overdue_open_source_count:
                        answer += " Certaines sources sont invalides ou dépassées; le planning réel reste incertain."
                captured = result.captured_at
            elif name == "REVENUE_SUMMARY":
                result = revenue_sources.read(db, principal.institute_id, request.ui_context.start, request.ui_context.end)
                captured = result.window.captured_at
                answer = "Facturation enregistrée sur la période sélectionnée, séparée par devise; encaissement et exhaustivité non établis."
            elif name == "REVENUE_LOSS_ANALYSIS":
                result = losses.read(db, principal.institute_id, request.ui_context.start, request.ui_context.end)
                captured = result.captured_at
                answer = "Annulations et absences enregistrées, avec les valeurs commerciales conservées. Perte financière causale indéterminée."
            elif name == "REVENUE_OPPORTUNITIES":
                if request.ui_context.opportunity_source == "closures":
                    result = opportunities.read_follow_ups(db, principal.institute_id, request.ui_context.start, request.ui_context.end)
                    answer = f"{result.booking_total} clôture(s) de rendez-vous et {result.walk_in_total} annulation(s) sans rendez-vous à examiner. Les valeurs conservées ne prouvent ni revenu récupérable ni permission de contact."
                elif request.ui_context.opportunity_source == "rebooking":
                    result = opportunities.read_returns(db, principal.institute_id)
                    answer = f"{result.total_candidates} reprise(s) à examiner selon les soins observés et la politique CRM; vérifiez les permissions de contact et les créneaux."
                else:
                    result = slot_opportunities.read(db, principal.institute_id, request.ui_context.service_id, request.ui_context.horizon_end)
                    answer = "Créneau projeté à examiner; vérifiez les horaires et la capacité avant toute affectation. Valeur financière inconnue."
                    if result.unavailable_reason:
                        answer = "Opportunité de capacité indisponible : " + result.unavailable_reason + "."
                captured = result.captured_at
            elif name in {"STOCK_READ", "STOCK_FORECAST"}:
                result = outlook.read(db, principal.institute_id, 50, 0,
                    request.ui_context.scenario if name == "STOCK_FORECAST" else None)
                captured = explicit_utc_instant(result.generated_at)
                answer = "Stocks enregistrés et commandes en attente, première page de 50 articles."
                if name == "STOCK_FORECAST":
                    answer = "Projection conditionnelle du scénario explicitement sélectionné; couverture des normes : " + result.coverage + ". Aucune commande créée."
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
