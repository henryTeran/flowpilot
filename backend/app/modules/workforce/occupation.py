from datetime import date
from typing import Literal
from pydantic import AwareDatetime, BaseModel
from sqlalchemy import select, union_all, literal, func, false, or_, and_
from app.modules.planning.models import ServiceSession
from app.modules.appointments.models import Appointment
from app.modules.workforce.models import EmployeeWorkInterval, WorkIntervalCancellation
from app.modules.workforce import work_hours
from app.modules.workforce.interval_math import union_intervals, intersection_duration, microseconds
from app.modules.workforce.schemas import MatrixPage
from app.shared.time import explicit_utc_instant


class OccupationSource(BaseModel):
    kind: Literal["session", "appointment"]
    id: str
    service_id: str
    status: str
    actual_start: AwareDatetime | None
    actual_end: AwareDatetime | None
    exclusion: Literal["missing_start", "missing_end", "invalid_interval", "future_end", "unfinalized"] | None
    clipped_start: AwareDatetime | None
    clipped_end: AwareDatetime | None
    duration_us: str | None


class EmployeeOccupation(BaseModel):
    work_hours: work_hours.EmployeeWorkHours
    page: MatrixPage
    rows: list[OccupationSource]
    diagnostics: dict[str, int]
    known_busy_duration_us: str
    covered_busy_duration_us: str
    outside_recorded_work_duration_us: str
    recorded_occupation_basis_points: str | None
    complete_activity: Literal[False] = False


def source_query(institute, employee, start, end):
    def candidate(first, last):
        return or_(and_(first.is_not(None), first < end, or_(last.is_(None), last > start,
                       and_(last <= first, first >= start))),
                   and_(first.is_(None), last > start, last <= end))
    session = select(literal("session").label("kind"), ServiceSession.id.label("id"), ServiceSession.service_id.label("service_id"),
        ServiceSession.status.label("status"), ServiceSession.start_time.label("first"), ServiceSession.real_end_time.label("last"))
    session = session.where(ServiceSession.institute_id == institute, ServiceSession.employee_id == employee,
        ServiceSession.status.in_(["completed", "in_progress", "extended", "delayed"]), candidate(ServiceSession.start_time, ServiceSession.real_end_time))
    appointment = select(literal("appointment"), Appointment.id, Appointment.service_id, Appointment.status,
        Appointment.actual_start_time, Appointment.actual_end_time).where(Appointment.institute_id == institute,
        Appointment.employee_id == employee, Appointment.status.in_(["completed", "in_progress"]),
        candidate(Appointment.actual_start_time, Appointment.actual_end_time))
    source = union_all(session, appointment).subquery()
    return source, (false() if end <= start else source.c.id.is_not(None))


def exclusion(first, last, status, now):
    if first is None: return "missing_start"
    if last is None: return "missing_end"
    if last <= first: return "invalid_interval"
    if last > now: return "future_end"
    if status != "completed": return "unfinalized"
    return None


def read(db, institute, employee, day, limit=20, offset=0, *, captured_at=None):
    # The hours authority holds the institute lock for this entire transaction.
    hours = work_hours.EmployeeWorkHours.model_validate(work_hours.read(db, institute, employee, day, captured_at=captured_at))
    start, end, now = hours.start, hours.end, hours.generated_at
    source, predicate = source_query(institute, employee, start, end)
    total = db.scalar(select(func.count()).select_from(source).where(predicate))
    diagnostics = {key: 0 for key in ("retained", "missing_start", "missing_end", "invalid_interval", "future_end", "unfinalized")}
    statement = select(source).where(predicate).order_by(source.c.first, source.c.kind, source.c.id)
    def busy_ranges(count=False):
        for row in db.execute(statement.execution_options(yield_per=100)).mappings():
            first = explicit_utc_instant(row["first"]) if row["first"] else None
            last = explicit_utc_instant(row["last"]) if row["last"] else None
            why = exclusion(first, last, row["status"], now)
            if count: diagnostics[why or "retained"] += 1
            if why is None:
                yield max(first, start), min(last, end)
    busy = sum(microseconds(a, b) for a, b in union_intervals(busy_ranges(count=True)))
    work, cancel = EmployeeWorkInterval, WorkIntervalCancellation
    work_statement = select(work.start_time, work.end_time).outerjoin(cancel,
        (cancel.institute_id == work.institute_id) & (cancel.work_interval_id == work.id)).where(work.institute_id == institute,
        work.employee_id == employee, cancel.id.is_(None), work.start_time < end, work.end_time > start,
        work.end_time <= now, false() if end <= start else work.id.is_not(None)).order_by(work.start_time, work.id)
    def work_ranges():
        for first, last in db.execute(work_statement.execution_options(yield_per=100)):
            yield max(explicit_utc_instant(first), start), min(explicit_utc_instant(last), end)
    covered = intersection_duration(union_intervals(work_ranges()), union_intervals(busy_ranges()))
    rows = []
    for row in db.execute(statement.limit(limit).offset(offset)).mappings():
        first = explicit_utc_instant(row["first"]) if row["first"] else None
        last = explicit_utc_instant(row["last"]) if row["last"] else None
        why = exclusion(first, last, row["status"], now)
        clipped_first, clipped_last = (max(first, start), min(last, end)) if why is None else (None, None)
        rows.append(dict(kind=row["kind"], id=row["id"], service_id=row["service_id"], status=row["status"], actual_start=first,
            actual_end=last, exclusion=why, clipped_start=clipped_first, clipped_end=clipped_last,
            duration_us=str(microseconds(clipped_first, clipped_last)) if why is None else None))
    uncertain = sum(value for key, value in diagnostics.items() if key != "retained")
    denominator = int(hours.recorded_duration_us) if hours.recorded_duration_us is not None else 0
    return dict(work_hours=hours, page=dict(offset=offset, limit=limit, total=total), rows=rows, diagnostics=diagnostics,
        known_busy_duration_us=str(busy), covered_busy_duration_us=str(covered), outside_recorded_work_duration_us=str(busy-covered),
        recorded_occupation_basis_points=str(covered*10000//denominator) if denominator and not uncertain else None, complete_activity=False)
