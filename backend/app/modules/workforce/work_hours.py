from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pydantic import AwareDatetime, BaseModel
from sqlalchemy import select, func, false
from app.modules.institutes.calendar import day_bounds
from app.modules.institutes.models import Institute
from app.modules.tickets.repository import lock_institute
from app.modules.workforce.models import EmployeeWorkInterval, WorkIntervalCancellation
from app.modules.workforce.objectives import require_employee
from app.modules.workforce.schemas import MatrixPage
from app.modules.workforce.work_interval_schemas import WorkIntervalRead, WorkIntervalCancellationRead
from app.shared.time import explicit_utc_instant, utcnow


class WorkHourSource(BaseModel):
    interval: WorkIntervalRead
    clipped_start: AwareDatetime
    clipped_end: AwareDatetime
    duration_us: str
    exclusion: Literal["cancelled", "future_end"] | None


class EmployeeWorkHours(BaseModel):
    institute_id: str
    employee_id: str
    day: date
    timezone: str
    start: AwareDatetime
    end: AwareDatetime
    generated_at: AwareDatetime
    page: MatrixPage
    rows: list[WorkHourSource]
    active_sources: int
    future_end_sources: int
    overlap_sources: int
    known_declared_duration_us: str
    known_union_duration_us: str
    recorded_duration_us: str | None
    complete_attendance: Literal[False] = False


def microseconds(start: datetime, end: datetime) -> int:
    delta = end-start
    return (delta.days*86400+delta.seconds)*1000000+delta.microseconds


def read(db, institute, employee, day, limit=20, offset=0):
    lock_institute(db, institute)
    require_employee(db, institute, employee)
    start, end = day_bounds(db, institute, day)
    now = utcnow()
    try:
        zone = ZoneInfo(db.get(Institute, institute).timezone).key
    except (ZoneInfoNotFoundError, ValueError):
        zone = "UTC"
    original, cancellation = EmployeeWorkInterval, WorkIntervalCancellation
    predicate = (original.institute_id == institute, original.employee_id == employee,
                 original.start_time < end, original.end_time > start, false() if end <= start else original.id.is_not(None))
    join = (cancellation.institute_id == original.institute_id) & (cancellation.work_interval_id == original.id)
    total = db.scalar(select(func.count()).select_from(original).where(*predicate))
    # Stream only endpoint pairs: exact integer arithmetic, O(1) aggregate memory,
    # no per-original query and no float/Julian-date loss on SQLite.
    endpoints = db.execute(select(original.start_time, original.end_time).outerjoin(cancellation, join)
        .where(*predicate, cancellation.id.is_(None)).order_by(original.start_time, original.id)
        .execution_options(yield_per=100))
    active = future = overlap = declared = union = 0
    union_end = None
    for first, last in endpoints:
        active += 1
        first, last = explicit_utc_instant(first), explicit_utc_instant(last)
        if last > now:
            future += 1
            continue
        first, last = max(first, start), min(last, end)
        if last <= first:
            continue
        declared += microseconds(first, last)
        if union_end is not None and first < union_end:
            overlap += 1
        uncovered = max(first, union_end) if union_end is not None else first
        if last > uncovered:
            union += microseconds(uncovered, last)
        union_end = max(last, union_end) if union_end is not None else last
    records = db.execute(select(original, cancellation).outerjoin(cancellation, join).where(*predicate)
        .order_by(original.start_time, original.id).limit(limit).offset(offset))
    rows = []
    for row, cancelled in records:
        value = WorkIntervalRead.model_validate(row)
        value.cancellation = WorkIntervalCancellationRead.model_validate(cancelled) if cancelled else None
        first, last = max(value.start_time, start), min(value.end_time, end)
        rows.append(dict(interval=value, clipped_start=first, clipped_end=last, duration_us=str(microseconds(first, last)),
                         exclusion="cancelled" if cancelled else "future_end" if value.end_time > now else None))
    return dict(institute_id=institute, employee_id=employee, day=day, timezone=zone, start=start, end=end, generated_at=now,
        page=dict(offset=offset, limit=limit, total=total), rows=rows, active_sources=active, future_end_sources=future,
        overlap_sources=overlap, known_declared_duration_us=str(declared), known_union_duration_us=str(union),
        recorded_duration_us=str(union) if active and not future else None, complete_attendance=False)
