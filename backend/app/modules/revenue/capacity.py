"""Recorded employee-time evidence; not a bookable resource-capacity forecast."""
from datetime import date
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pydantic import field_validator
from sqlalchemy import select
from app.modules.crm.metrics import Fact, Identifier, Count, Unsigned, ExactRatio
from app.modules.employees.models import Employee
from app.modules.institutes.calendar import day_bounds
from app.modules.institutes.models import Institute
from app.modules.revenue.billing import Window
from app.modules.tickets.repository import lock_institute
from app.modules.workforce import occupation
from app.modules.workforce.schemas import MatrixPage
from app.shared.exceptions import business_error
from app.shared.time import utcnow


class EmployeeMeasure(Fact):
    employee_id: Identifier
    evidence: occupation.EmployeeOccupation
    recorded_unoccupied_duration_us: Unsigned | None
    recorded_utilization_ratio: ExactRatio | None


class Capacity(Fact):
    window: Window
    day: date
    timezone: str
    basis: Literal["declared_work_intersected_with_finalized_recorded_activity"] = "declared_work_intersected_with_finalized_recorded_activity"
    page: MatrixPage
    rows: tuple[EmployeeMeasure, ...]
    employee_count: Count
    employees_without_usable_hours: Count
    employees_with_uncertain_activity: Count
    known_declared_union_duration_us: Unsigned
    known_covered_busy_duration_us: Unsigned
    known_outside_declared_work_duration_us: Unsigned
    recorded_unoccupied_duration_us: Unsigned | None
    recorded_utilization_ratio: ExactRatio | None
    complete_attendance: Literal[False] = False
    complete_activity: Literal[False] = False
    physical_unused_capacity: None = None
    bookable_capacity: None = None
    estimated_value: None = None

    @field_validator("complete_attendance", "complete_activity", mode="before")
    @classmethod
    def no_claim(cls, value):
        if value is not False:
            raise ValueError("Recorded sources cannot prove complete physical activity")
        return value


def measure(employee, evidence):
    evidence = occupation.EmployeeOccupation.model_validate(evidence.model_dump())
    hours = evidence.work_hours
    if hours.employee_id != employee:
        raise ValueError("Employee occupation evidence belongs to another employee")
    uncertain = sum(value for key, value in evidence.diagnostics.items() if key != "retained")
    usable = hours.recorded_duration_us is not None and not uncertain
    work, busy = int(hours.recorded_duration_us or "0"), int(evidence.covered_busy_duration_us)
    if busy > int(hours.known_union_duration_us):
        raise ValueError("Covered activity cannot exceed declared work")
    return EmployeeMeasure(employee_id=employee, evidence=evidence,
        recorded_unoccupied_duration_us=str(work-busy) if usable else None,
        recorded_utilization_ratio=ExactRatio(numerator=str(busy), denominator=str(work)) if usable and work else None)


def read(db, institute, day, offset=0, limit=20):
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 50:
        raise business_error("Invalid capacity page bounds")
    lock_institute(db, institute)
    now = utcnow()
    try:
        zone = ZoneInfo(db.get(Institute, institute).timezone).key
    except (ZoneInfoNotFoundError, ValueError, TypeError) as error:
        raise business_error("An explicit valid institute timezone is required") from error
    start, end = day_bounds(db, institute, day)
    try:
        window = Window(institute_id=institute, start=start, end=end, captured_at=now)
    except ValueError as error:
        raise business_error("An observed positive institute day is required") from error
    total = missing = uncertain = work = busy = outside = 0
    rows = []
    # Aggregate all owned employees, including unavailable/archived historical
    # staff. Page limits bound returned evidence, never the institute denominator.
    for employee in db.scalars(select(Employee.id).where(Employee.institute_id == institute)
        .order_by(Employee.id).execution_options(yield_per=100)):
        evidence = occupation.EmployeeOccupation.model_validate(occupation.read(db, institute, employee, day,
            limit=1, captured_at=now))
        if evidence.work_hours.generated_at != now or evidence.work_hours.start != start or evidence.work_hours.end != end:
            raise business_error("Capacity evidence capture requires verification")
        row = measure(employee, evidence)
        missing += evidence.work_hours.recorded_duration_us is None
        uncertain += any(value for key, value in evidence.diagnostics.items() if key != "retained")
        work += int(evidence.work_hours.known_union_duration_us)
        busy += int(evidence.covered_busy_duration_us)
        outside += int(evidence.outside_recorded_work_duration_us)
        if offset <= total < offset+limit:
            rows.append(row)
        total += 1
    usable = total > 0 and not missing and not uncertain
    return Capacity(window=window, day=day, timezone=zone, page=MatrixPage(offset=offset, limit=limit, total=total), rows=tuple(rows),
        employee_count=total, employees_without_usable_hours=missing, employees_with_uncertain_activity=uncertain,
        known_declared_union_duration_us=str(work), known_covered_busy_duration_us=str(busy),
        known_outside_declared_work_duration_us=str(outside), recorded_unoccupied_duration_us=str(work-busy) if usable else None,
        recorded_utilization_ratio=ExactRatio(numerator=str(busy), denominator=str(work)) if usable and work else None)
