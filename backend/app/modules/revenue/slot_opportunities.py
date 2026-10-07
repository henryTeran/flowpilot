"""A new walk-in projection through the sovereign queue/resource engine."""
from datetime import timedelta, datetime
from typing import Literal
from pydantic import AwareDatetime, Field, field_validator
from sqlalchemy import select
from app.modules.crm.metrics import Fact, Identifier, Count
from app.modules.services.models import Service
from app.modules.resources.repository import requirement_facts, resource_requirement_facts
from app.modules.scheduling.waiting_service import waiting_projections
from app.modules.tickets.repository import lock_institute
from app.shared.exceptions import business_error, not_found
from app.shared.time import utcnow


class Need(Fact):
    kind: Literal["room", "equipment", "bed", "chair", "device"]
    capability: str
    quantity: int = Field(strict=True, ge=1, le=10)


class Evidence(Fact):
    institute_id: Identifier
    captured_at: AwareDatetime
    horizon_end: AwareDatetime
    service_id: Identifier
    duration_minutes: int = Field(strict=True, gt=0)
    required_skills: tuple[str, ...]
    resource_needs: tuple[Need, ...]
    prior_queue_count: Count
    unprojectable_prior_queue_count: Count
    employee_id: Identifier
    projected_start: AwareDatetime
    projected_end: AwareDatetime


class Opportunity(Fact):
    type: Literal["review_projected_walk_in_slot"] = "review_projected_walk_in_slot"
    evidence: Evidence
    estimated_value: None = None
    confidence: Literal["conditional_current_queue_projection"] = "conditional_current_queue_projection"
    recommended_action: Literal["review_opening_hours_and_revalidate_capacity_before_assignment"] = "review_opening_hours_and_revalidate_capacity_before_assignment"
    capacity_reserved: Literal[False] = False
    action_executed: Literal[False] = False

    @field_validator("capacity_reserved", "action_executed", mode="before")
    @classmethod
    def no_action(cls, value):
        if value is not False:
            raise ValueError("A projection cannot reserve capacity or execute assignment")
        return value


class Read(Fact):
    institute_id: Identifier
    service_id: Identifier
    captured_at: AwareDatetime
    horizon_end: AwareDatetime
    opportunity: Opportunity | None
    unavailable_reason: Literal["resource_configuration_missing", "capacity_unknown", "outside_horizon"] | None


def read(db, institute, service_id, horizon_end):
    lock_institute(db, institute)
    now = utcnow()
    if not isinstance(horizon_end, datetime) or horizon_end.utcoffset() is None or horizon_end <= now:
        raise business_error("An explicit positive future capacity horizon is required")
    service = db.scalar(select(Service).where(Service.id == service_id, Service.status == "active")
        .execution_options(populate_existing=True))
    if service is None:
        raise not_found("Prestation active introuvable")
    if type(service.duration_min) is not int or service.duration_min <= 0:
        raise business_error("Recorded service duration requires verification")
    needs = resource_requirement_facts(db, institute).get(service_id, [])
    reason = "resource_configuration_missing" if service.requires_machine and not needs else None
    opportunity = None
    if reason is None:
        try:
            projections = waiting_projections(db, institute, now=now, new_duration=service.duration_min, new_service_ids=[service_id])
            result = projections["__new_arrival__"]
            if result.reason != "projected":
                reason = "capacity_unknown"
            elif result.estimated_start_time is None or result.estimated_end_time is None or result.employee_id is None \
                    or result.estimated_start_time < now \
                    or result.estimated_end_time-result.estimated_start_time != timedelta(minutes=service.duration_min):
                raise ValueError("Core projection must preserve the captured duration and chronology")
            elif result.estimated_end_time > horizon_end:
                reason = "outside_horizon"
            else:
                prior = [row for key, row in projections.items() if key != "__new_arrival__"]
                opportunity = Opportunity(evidence=Evidence(institute_id=institute, captured_at=now, horizon_end=horizon_end,
                    service_id=service_id, duration_minutes=service.duration_min,
                    required_skills=tuple(sorted(requirement_facts(db, institute, [service_id]).get(service_id, set()))),
                    resource_needs=tuple(Need(kind=kind, capability=capability, quantity=quantity) for kind, capability, quantity in sorted(needs)),
                    prior_queue_count=len(prior), unprojectable_prior_queue_count=sum(row.reason != "projected" for row in prior),
                    employee_id=result.employee_id, projected_start=result.estimated_start_time, projected_end=result.estimated_end_time))
        except (ValueError, OverflowError, KeyError) as error:
            raise business_error("Core capacity projection requires verification") from error
    return Read(institute_id=institute, service_id=service_id, captured_at=now, horizon_end=horizon_end,
        opportunity=opportunity, unavailable_reason=reason)
