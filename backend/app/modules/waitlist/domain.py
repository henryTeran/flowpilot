"""Pure matching of declared demand against captured domain capacity.

Adapters must authenticate source scope and completeness. This kernel neither
loads SQL nor infers opening hours, contact authority or a reservation.
"""
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, StringConstraints, field_validator, model_validator
from app.modules.crm.metrics import Fact as BaseFact, Identifier
from app.modules.resources.domain import has_required_skills
from app.modules.resources.allocation_domain import (
    ResourceNeed, ResourceTimeline, next_resource_window,
)
from app.modules.scheduling.availability_domain import free_windows

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=240)]
Minutes = Annotated[int, Field(strict=True, gt=0, le=1440)]


class Fact(BaseFact):
    @field_validator("*", mode="after")
    @classmethod
    def elapsed_instants(cls, value):
        # Equal ZoneInfo objects compare wall clocks across a repeated hour;
        # business intervals must instead compare elapsed instants.
        if isinstance(value, datetime):
            return value.astimezone(timezone.utc)
        return value


class Window(Fact):
    start: AwareDatetime
    end: AwareDatetime

    @model_validator(mode="after")
    def positive(self):
        if self.end <= self.start:
            raise ValueError("A positive half-open availability interval is required")
        return self


def validate_windows(windows):
    if not windows:
        raise ValueError("At least one explicit window is required")
    if any(left.end > right.start for left, right in zip(windows, windows[1:])):
        raise ValueError("Windows must be ordered and non-overlapping")


class Demand(Fact):
    institute_id: Identifier
    customer_id: Identifier
    service_id: Identifier
    declared_at: AwareDatetime
    duration_minutes: Minutes
    availability: tuple[Window, ...] = Field(min_length=1, max_length=64)
    # Empty means explicitly no employee restriction, not an unknown preference.
    allowed_employee_ids: tuple[Identifier, ...] = Field(max_length=100)
    constraints_review: Literal["confirmed", "unknown"]
    availability_evidence: Text
    constraints_evidence: Text | None

    @model_validator(mode="after")
    def coherent(self):
        validate_windows(self.availability)
        if len(set(self.allowed_employee_ids)) != len(self.allowed_employee_ids):
            raise ValueError("Employee restrictions must be unique")
        if (self.constraints_review == "confirmed") != (self.constraints_evidence is not None):
            raise ValueError("Confirmed constraints require evidence; unknown stays unknown")
        if any(window.end <= self.declared_at for window in self.availability):
            raise ValueError("Declared availability must extend beyond declaration capture")
        return self


class Need(Fact):
    kind: Literal["room", "equipment", "bed", "chair", "device"]
    capability: str
    quantity: Annotated[int, Field(strict=True, ge=1, le=10)]


class ServiceCapacity(Fact):
    service_id: Identifier
    duration_minutes: Minutes
    required_skills: tuple[Identifier, ...]
    needs: tuple[Need, ...]
    resource_configuration: Literal["known", "unknown"]

    @model_validator(mode="after")
    def unique(self):
        if len(set(self.required_skills)) != len(self.required_skills):
            raise ValueError("Skill requirements must be unique")
        if len({(need.kind, need.capability) for need in self.needs}) != len(self.needs):
            raise ValueError("Resource requirements must be unique")
        return self


class EmployeeCapacity(Fact):
    employee_id: Identifier
    skills: tuple[Identifier, ...]
    # Empty with known means no usable window; unknown cannot become free capacity.
    state: Literal["known", "unknown"]
    windows: tuple[Window, ...]

    @model_validator(mode="after")
    def coherent(self):
        if self.windows:
            validate_windows(self.windows)
        if self.state == "unknown" and self.windows:
            raise ValueError("Unknown employee capacity cannot expose free windows")
        if len(set(self.skills)) != len(self.skills):
            raise ValueError("Employee skills must be unique")
        return self


class ResourceCapacity(Fact):
    resource_id: Identifier
    kind: Literal["room", "equipment", "bed", "chair", "device"]
    capabilities: tuple[str, ...]
    state: Literal["active_known", "inactive", "unknown"]
    reservations: tuple[Window, ...]


class CustomerContext(Fact):
    customer_id: Identifier
    history: Literal["observed", "no_recorded_care", "unknown"]
    history_reference: Identifier | None
    history_at: AwareDatetime | None
    permission: Literal["granted", "refused", "unknown"]
    channel: Literal["email", "sms"]
    purpose: Literal["service_follow_up"] = "service_follow_up"
    permission_at: AwareDatetime | None
    permission_reference: Identifier | None

    @model_validator(mode="after")
    def coherent(self):
        if self.history == "observed":
            if self.history_reference is None or self.history_at is None:
                raise ValueError("Observed history requires a dated source reference")
        elif self.history_reference is not None or self.history_at is not None:
            raise ValueError("Unknown/absent history cannot invent a care source")
        if self.permission == "unknown":
            if self.permission_at is not None or self.permission_reference is not None:
                raise ValueError("Unknown permission cannot claim a declaration")
        elif self.permission_at is None or self.permission_reference is None:
            raise ValueError("Permission/refusal requires a dated source reference")
        return self


class Capture(Fact):
    institute_id: Identifier
    captured_at: AwareDatetime
    service: ServiceCapacity
    employees: tuple[EmployeeCapacity, ...]
    resources: tuple[ResourceCapacity, ...]
    customer: CustomerContext
    customer_capacity: Literal["known", "unknown"] = "known"
    customer_blockers: tuple[Window, ...] = ()
    queue_capacity: Literal["known", "unknown"] = "known"

    @model_validator(mode="after")
    def coherent(self):
        for rows, key in ((self.employees, "employee_id"), (self.resources, "resource_id")):
            if len({getattr(row, key) for row in rows}) != len(rows):
                raise ValueError("Capacity source identities must be unique")
        for instant in (self.customer.history_at, self.customer.permission_at):
            if instant is not None and instant > self.captured_at:
                raise ValueError("Future customer declarations/history are not current evidence")
        return self


class Option(Fact):
    employee_id: Identifier
    start: AwareDatetime
    end: AwareDatetime
    resource_ids: tuple[Identifier, ...]


class Review(Fact):
    demand: Demand
    capture: Capture
    options: tuple[Option, ...]
    unavailable_reason: Literal["constraints_unknown", "duration_changed", "resource_configuration_unknown", "customer_capacity_unknown", "queue_projection_unknown", "no_matching_recorded_capacity"] | None
    confidence: Literal["conditional_recorded_capacity"] = "conditional_recorded_capacity"
    # Literal string avoids bool coercion; there is no action path in this kernel.
    action: Literal["manual_review_only"] = "manual_review_only"


def match(demand: Demand, capture: Capture) -> Review:
    # Revalidate unsafe copied models before applying any business rule.
    demand = Demand.model_validate(demand.model_dump())
    capture = Capture.model_validate(capture.model_dump())
    if demand.institute_id != capture.institute_id or demand.customer_id != capture.customer.customer_id \
            or demand.service_id != capture.service.service_id or demand.declared_at > capture.captured_at:
        raise ValueError("Demand and source capture must share scope, service and chronology")
    reason = None
    if demand.constraints_review == "unknown":
        reason = "constraints_unknown"
    elif demand.duration_minutes != capture.service.duration_minutes:
        reason = "duration_changed"
    elif capture.service.resource_configuration == "unknown":
        reason = "resource_configuration_unknown"
    elif capture.customer_capacity == "unknown":
        reason = "customer_capacity_unknown"
    elif capture.queue_capacity == "unknown":
        reason = "queue_projection_unknown"
    options = []
    if reason is None:
        resources = tuple(ResourceTimeline(row.resource_id, row.kind, frozenset(row.capabilities),
            tuple((window.start, window.end) for window in row.reservations),
            row.state != "inactive", row.state == "active_known") for row in capture.resources)
        needs = tuple(ResourceNeed(row.kind, row.capability, row.quantity) for row in capture.service.needs)
        for employee in capture.employees:
            if employee.state != "known" or demand.allowed_employee_ids and employee.employee_id not in demand.allowed_employee_ids \
                    or not has_required_skills(employee.skills, capture.service.required_skills):
                continue
            for available in demand.availability:
                for free in employee.windows:
                    start = max(available.start, free.start, capture.captured_at)
                    end = min(available.end, free.end)
                    if end - start < timedelta(minutes=demand.duration_minutes):
                        continue
                    blockers = [(window.start, window.end, str(index)) for index, window in enumerate(capture.customer_blockers)]
                    for begin, finish, _ in free_windows(start, blockers):
                        finish = min(finish, end) if finish is not None else end
                        if finish-begin < timedelta(minutes=demand.duration_minutes):
                            continue
                        result = next_resource_window(resources, needs, begin, demand.duration_minutes, latest_end=finish)
                        if result is not None:
                            options.append(Option(employee_id=employee.employee_id, start=result.start,
                                end=result.end, resource_ids=result.resource_ids))
        # Earliest complete option for each window intersection; not every possible
        # appointment start, and no revenue/history/consent score is invented.
        options = sorted(set((row.employee_id, row.start, row.end, row.resource_ids) for row in options),
            key=lambda row: (row[1], row[0], row[2], row[3]))
        options = [Option(employee_id=row[0], start=row[1], end=row[2], resource_ids=row[3]) for row in options]
        if not options:
            reason = "no_matching_recorded_capacity"
    return Review(demand=demand, capture=capture, options=tuple(options), unavailable_reason=reason)
