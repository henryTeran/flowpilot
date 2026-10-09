"""Scoped employee commitment overlaps, with original source references."""
from datetime import date
from typing import Literal
from pydantic import AwareDatetime, model_validator
from sqlalchemy import select
from app.modules.appointments.models import Appointment
from app.modules.employees.models import Employee
from app.modules.planning.models import ServiceSession
from app.modules.workforce.models import EmployeeAbsence, AbsenceCancellation
from app.modules.scheduling.repository import ACTIVE_APPOINTMENT_STATUSES, ACTIVE_SESSION_STATUSES
from app.modules.workforce.interval_math import intersection_duration
from app.modules.institutes.calendar import day_bounds
from app.modules.tickets.repository import lock_institute
from app.modules.crm.metrics import Fact, Identifier, Count, Unsigned
from app.modules.waitlist.originals import fingerprint
from app.shared.exceptions import business_error, not_found
from app.shared.time import explicit_utc_instant, utcnow


class Commitment(Fact):
    kind: Literal["appointment", "session", "absence"]
    id: Identifier
    start_at: AwareDatetime
    end_at: AwareDatetime

    @model_validator(mode="after")
    def positive(self):
        if not self.start_at < self.end_at:
            raise ValueError("A positive commitment interval is required")
        return self


class Overlap(Fact):
    left: Commitment
    right: Commitment
    start_at: AwareDatetime
    end_at: AwareDatetime
    duration_us: Unsigned

    @model_validator(mode="after")
    def exact_overlap(self):
        if (not self.start_at < self.end_at or self.start_at < max(self.left.start_at, self.right.start_at)
            or self.end_at > min(self.left.end_at, self.right.end_at)
            or int(self.duration_us) != intersection_duration([(self.start_at, self.end_at)], [(self.start_at, self.end_at)])):
            raise ValueError("Overlap must be a positive exact intersection of its sources")
        return self


class Read(Fact):
    institute_id: Identifier
    employee_id: Identifier
    day: date
    captured_at: AwareDatetime
    start_at: AwareDatetime
    end_at: AwareDatetime
    source_digest: str
    source_count: Count
    invalid_source_count: Count
    overdue_open_source_count: Count
    overlap_count: Count
    overlaps: tuple[Overlap, ...]
    page_limit: Literal[50] = 50
    basis: Literal["current_recorded_employee_commitments_half_open"] = "current_recorded_employee_commitments_half_open"
    resource_conflicts_covered: Literal[False] = False
    physical_activity_proven: Literal[False] = False


def overlaps(sources, start, end):
    """Clip to the selected institute day and reuse exact interval arithmetic."""
    sources = sorted(sources, key=lambda s: (s.start_at, s.kind, s.id))
    for index, left in enumerate(sources):
        for right in sources[index+1:]:
            if right.start_at >= min(left.end_at, end):
                break
            if left.kind == right.kind == "absence":
                continue  # Redundant absence declarations are not two service obligations.
            first, last = max(start, left.start_at, right.start_at), min(end, left.end_at, right.end_at)
            duration = intersection_duration([(max(start, left.start_at), min(end, left.end_at))],
                [(max(start, right.start_at), min(end, right.end_at))])
            if duration:
                yield Overlap(left=left, right=right, start_at=first, end_at=last, duration_us=str(duration))


def read(db, institute, employee, day):
    lock_institute(db, institute)
    owned = db.scalar(select(Employee.id).where(Employee.id == employee, Employee.institute_id == institute))
    if owned is None:
        raise not_found("Selected employee not found")
    start, end = day_bounds(db, institute, day)
    captured = utcnow()
    queries = (
        ("appointment", select(Appointment.id, Appointment.start_time, Appointment.end_time).where(
            Appointment.institute_id == institute, Appointment.employee_id == employee,
            Appointment.status.in_(ACTIVE_APPOINTMENT_STATUSES))),
        ("session", select(ServiceSession.id, ServiceSession.start_time, ServiceSession.planned_end_time).where(
            ServiceSession.institute_id == institute, ServiceSession.employee_id == employee,
            ServiceSession.status.in_(ACTIVE_SESSION_STATUSES))),
        ("absence", select(EmployeeAbsence.id, EmployeeAbsence.start_time, EmployeeAbsence.end_time).outerjoin(
            AbsenceCancellation, (AbsenceCancellation.institute_id == institute)
            & (AbsenceCancellation.absence_id == EmployeeAbsence.id)).where(EmployeeAbsence.institute_id == institute,
            EmployeeAbsence.employee_id == employee, AbsenceCancellation.id.is_(None))),
    )
    sources = []
    invalid = overdue = scanned = 0
    for kind, statement in queries:
        for identifier, first, last in db.execute(statement.execution_options(yield_per=100)):
            scanned += 1
            if scanned > 1000:
                raise business_error("Employee commitment capture exceeds supported source bound")
            try:
                source = Commitment(kind=kind, id=identifier, start_at=explicit_utc_instant(first), end_at=explicit_utc_instant(last))
            except (ValueError, TypeError):
                invalid += 1
                continue
            if source.start_at < end and source.end_at > start:
                sources.append(source)
                overdue += int(kind != "absence" and source.end_at <= captured)
    sources.sort(key=lambda s: (s.start_at, s.kind, s.id))
    page = []
    total = 0
    for overlap in overlaps(sources, start, end):
        total += 1
        if len(page) < 50:
            page.append(overlap)
    return Read(institute_id=institute, employee_id=employee, day=day, captured_at=captured, start_at=start, end_at=end,
        source_digest=fingerprint([s.model_dump(mode="json") for s in sources]), source_count=len(sources),
        invalid_source_count=invalid, overdue_open_source_count=overdue, overlap_count=total, overlaps=tuple(page))
