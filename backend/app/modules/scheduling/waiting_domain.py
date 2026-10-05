"""Pure, deterministic queue projection. Estimates never authorize a write."""
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class EmployeeTimeline:
    employee_id: str
    available_from: datetime
    appointments: tuple[tuple[datetime, datetime], ...] = ()


@dataclass(frozen=True)
class QueueWork:
    ticket_id: str
    duration_minutes: int
    assigned_employee_id: str | None = None


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


def project_queue(employees: list[EmployeeTimeline], queue: list[QueueWork]) -> dict[str, WaitProjection]:
    timelines = {employee.employee_id: employee for employee in employees}
    cursors = {employee.employee_id: employee.available_from for employee in employees}
    results = {}
    # An explicit assignment already reserves capacity. Preserve FIFO within each
    # group, and do not let unassigned projections consume that reservation.
    ordered = [work for work in queue if work.assigned_employee_id]
    ordered += [work for work in queue if not work.assigned_employee_id]
    for work in ordered:
        candidates = [work.assigned_employee_id] if work.assigned_employee_id else list(timelines)
        starts = [(next_fitting_start(cursors[employee_id], work.duration_minutes,
                                      timelines[employee_id].appointments), employee_id)
                  for employee_id in candidates if employee_id in timelines and work.duration_minutes > 0]
        if not starts:
            results[work.ticket_id] = WaitProjection(work.ticket_id, None, None, None, "capacity_unknown")
            continue
        start, employee_id = min(starts)
        end = start + timedelta(minutes=work.duration_minutes)
        cursors[employee_id] = end
        results[work.ticket_id] = WaitProjection(work.ticket_id, employee_id, start, end, "projected")
    return results
