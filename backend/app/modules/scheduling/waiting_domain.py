"""Pure, deterministic queue projection. Estimates never authorize a write."""
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from app.modules.resources.allocation_domain import ResourceNeed, ResourceTimeline, next_resource_window


@dataclass(frozen=True)
class EmployeeTimeline:
    employee_id: str
    available_from: datetime
    appointments: tuple[tuple[datetime, datetime], ...] = ()
    skills: frozenset[str] = frozenset()


@dataclass(frozen=True)
class QueueWork:
    ticket_id: str
    duration_minutes: int
    assigned_employee_id: str | None = None
    required_skills: frozenset[str] = frozenset()
    resource_capacity_known: bool = True
    resource_needs: tuple[ResourceNeed, ...] = ()
    owned_reservations: tuple[tuple[str, datetime, datetime], ...] = ()


@dataclass(frozen=True)
class WaitProjection:
    ticket_id: str
    employee_id: str | None
    estimated_start_time: datetime | None
    estimated_end_time: datetime | None
    reason: str


def next_fitting_start(start: datetime, duration: int, appointments) -> datetime:
    if duration <= 0:
        raise ValueError("Service duration must be positive")
    for booked_start, booked_end in sorted(appointments):
        if booked_end <= start:
            continue
        if start + timedelta(minutes=duration) <= booked_start:
            break
        start = max(start, booked_end)
    return start


def project_queue(employees: list[EmployeeTimeline], queue: list[QueueWork],
                  resources: tuple[ResourceTimeline, ...] = (), *, _allocation_observer=None) -> dict[str, WaitProjection]:
    timelines = {employee.employee_id: employee for employee in employees}
    cursors = {employee.employee_id: employee.available_from for employee in employees}
    results = {}
    # An explicit assignment already reserves capacity. Preserve FIFO within each
    # group, and do not let unassigned projections consume that reservation.
    ordered = [work for work in queue if work.assigned_employee_id]
    ordered += [work for work in queue if not work.assigned_employee_id]
    for work in ordered:
        candidates = [work.assigned_employee_id] if work.assigned_employee_id else list(timelines)
        # Ignore only this ticket's persisted reservation while recalculating it.
        # Other commitments remain intact if this ticket cannot be projected.
        usable = tuple(replace(resource, reservations=tuple(interval for interval in resource.reservations
            if (resource.resource_id, *interval) not in work.owned_reservations)) for resource in resources)
        starts = []
        matches = {}
        for employee_id in candidates:
            if employee_id not in timelines or work.duration_minutes <= 0 or not work.resource_capacity_known:
                continue
            employee = timelines[employee_id]
            if not work.required_skills.issubset(employee.skills):
                continue
            start = cursors[employee_id]
            while True:
                start = next_fitting_start(start, work.duration_minutes, employee.appointments)
                match = next_resource_window(usable, work.resource_needs, start, work.duration_minutes)
                if match is None:
                    break
                fitted = next_fitting_start(match.start, work.duration_minutes, employee.appointments)
                if fitted == match.start:
                    starts.append((match.start, employee_id))
                    matches[employee_id] = match
                    break
                start = fitted
        if not starts:
            reason = "capacity_unknown" if work.resource_capacity_known else "resource_capacity_unknown"
            results[work.ticket_id] = WaitProjection(work.ticket_id, None, None, None, reason)
            continue
        start, employee_id = min(starts)
        end = start + timedelta(minutes=work.duration_minutes)
        selected = matches[employee_id].resource_ids
        resources = tuple(replace(resource, reservations=resource.reservations + ((start, end),))
                          if resource.resource_id in selected else resource for resource in usable)
        cursors[employee_id] = end
        results[work.ticket_id] = WaitProjection(work.ticket_id, employee_id, start, end, "projected")
        if _allocation_observer is not None:
            _allocation_observer(results[work.ticket_id], matches[employee_id])
    return results
