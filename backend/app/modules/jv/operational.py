"""Descriptive rules over captured service facts, never an eligibility engine.

This internal boundary accepts trusted server evidence, not public client claims.
Its hashes detect changes; they neither authenticate a source nor prove freshness.
"""
from typing import Annotated, Literal
from pydantic import Field
from app.modules.base import query
from app.modules.base.analysis_contract import Analysis
from app.modules.base.read_capabilities import Digest, ExactId
from app.modules.crm.metrics import Fact
from app.modules.waitlist.originals import fingerprint

Count = Annotated[int, Field(strict=True, ge=0)]
MetricName = Literal["queue_tickets", "assigned_queue_tickets", "available_employees",
    "upcoming_slots", "assignment_options", "assignable_options", "planning_employees", "planning_sessions"]


class Citation(Fact):
    evidence_fingerprint: Digest
    pointer: str


class Metric(Fact):
    name: MetricName
    value: Count
    unit: Literal["count"] = "count"
    basis: Literal["captured_service_fact_count"] = "captured_service_fact_count"
    sources: tuple[Citation, ...]


class AvailabilityDiagnostic(Fact):
    employee_id: ExactId
    available: bool
    reason: str | None
    sources: tuple[Citation, ...]


class AssignmentDiagnostic(Fact):
    employee_id: ExactId
    assignable: bool
    reason: str
    sources: tuple[Citation, ...]


class OperationalAnalysis(Analysis):
    institute_id: ExactId
    capability: query.Name
    rule_version: Literal["jv.operational.v1"] = "jv.operational.v1"
    metrics: tuple[Metric, ...]
    availability: AvailabilityDiagnostic | None = None
    assignments: tuple[AssignmentDiagnostic, ...] = ()
    actions: tuple[()] = ()
    interpretation: Literal["descriptive_snapshot_not_prediction_causality_or_execution"] = "descriptive_snapshot_not_prediction_causality_or_execution"
    fingerprint: Digest


def verified(candidate: query.Evidence) -> query.Evidence:
    # Reconstruct nested models, including objects made with unchecked model_copy.
    evidence = query.Evidence.model_validate(candidate.model_dump(mode="json"))
    body = evidence.model_dump(mode="json", exclude={"fingerprint"})
    if fingerprint(body) != evidence.fingerprint:
        raise ValueError("JV evidence digest mismatch")
    if evidence.capability != query.REGISTRY[evidence.capability.name]:
        raise ValueError("JV capability metadata mismatch")
    if not isinstance(evidence.result, query.OUTPUTS[evidence.capability.name]):
        raise ValueError("JV capability/result mismatch")
    if evidence.captured_at > evidence.read_completed_at:
        raise ValueError("JV evidence chronology mismatch")
    result = evidence.result
    if isinstance(result, query.AvailabilityFacts):
        slots = (result.current_slot,) if result.current_slot else ()
        slots += result.upcoming_slots
        if result.institute_id != evidence.institute_id or any(
            s.institute_id != evidence.institute_id or s.employee_id != result.employee_id for s in slots):
            raise ValueError("JV availability scope mismatch")
    if isinstance(result, query.AssignmentFacts) and any(
        o.institute_id != evidence.institute_id or o.ticket_id != result.ticket_id for o in result.options):
        raise ValueError("JV assignment scope mismatch")
    if isinstance(result, query.PlanningFacts) and any(
        s.employee_id != row.employee_id for row in result.rows for s in row.sessions):
        raise ValueError("JV planning ownership mismatch")
    return evidence


class OperationalAnalyzer:
    def analyze(self, candidate: query.Evidence) -> OperationalAnalysis:
        evidence = verified(candidate)
        result = evidence.result
        digest = evidence.fingerprint
        def cite(pointer):
            return Citation(evidence_fingerprint=digest, pointer=pointer)
        def metric(name, value, pointer):
            return Metric(name=name, value=value, sources=(cite(pointer),))
        availability = None
        assignments = ()
        if isinstance(result, query.QueueFacts):
            metrics = (metric("queue_tickets", len(result.items), "/result/items"),
                metric("assigned_queue_tickets", sum(i.assigned_employee_id is not None for i in result.items), "/result/items"))
        elif isinstance(result, query.AvailabilityFacts):
            metrics = (metric("available_employees", int(result.available), "/result/available"),
                metric("upcoming_slots", len(result.upcoming_slots), "/result/upcoming_slots"))
            availability = AvailabilityDiagnostic(employee_id=result.employee_id, available=result.available,
                reason=result.current_slot.reason if result.current_slot else None,
                sources=(cite("/result/available"), cite("/result/current_slot")))
        elif isinstance(result, query.AssignmentFacts):
            metrics = (metric("assignment_options", len(result.options), "/result/options"),
                metric("assignable_options", sum(o.assignable for o in result.options), "/result/options"))
            assignments = tuple(AssignmentDiagnostic(employee_id=o.employee_id, assignable=o.assignable,
                reason=o.reason, sources=(cite(f"/result/options/{index}"),)) for index, o in enumerate(result.options))
        else:
            metrics = (metric("planning_employees", len(result.rows), "/result/rows"),
                metric("planning_sessions", sum(len(row.sessions) for row in result.rows), "/result/rows"))
        analysis = OperationalAnalysis(institute_id=evidence.institute_id, capability=evidence.capability.name,
            evidence_fingerprint=digest, observed_facts=tuple(m.name for m in metrics),
            missing_facts=("revenue", "unobserved_demand", "causal_contributions", "future_availability"),
            metrics=metrics, availability=availability, assignments=assignments, fingerprint="0" * 64)
        return analysis.model_copy(update={"fingerprint": fingerprint(analysis.model_dump(mode="json", exclude={"fingerprint"}))})
