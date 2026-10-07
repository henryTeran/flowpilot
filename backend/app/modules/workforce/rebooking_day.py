"""Recorded declaration day, distinct from execution or booking slot day."""
from datetime import date
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pydantic import BaseModel, AwareDatetime
from sqlalchemy import select, false
from app.modules.workforce.rebooking import RebookingRead, dto
from app.modules.workforce.models import EmployeeRebooking as Original, RebookingCancellation as Cancellation
from app.modules.appointments.models import Appointment
from app.modules.institutes.models import Institute
from app.modules.institutes.calendar import day_bounds
from app.modules.workforce.objectives import require_employee
from app.modules.workforce.schemas import MatrixPage
from app.modules.tickets.repository import lock_institute
from app.shared.time import utcnow, explicit_utc_instant
from app.modules.workforce.rebooking_sources import ExecutionCapture, BookingCapture

State = Literal["cancelled_declaration", "future_recording", "unknown_target", "cancelled_booking", "no_show", "booked_return", "completed_return"]
STATES = ("cancelled_declaration", "future_recording", "unknown_target", "cancelled_booking", "no_show", "booked_return", "completed_return")


class DayRow(BaseModel):
    original: RebookingRead
    target_status: str | None
    target_customer_id: str | None
    actual_start: AwareDatetime | None
    actual_end: AwareDatetime | None
    state: State


class RebookingDay(BaseModel):
    institute_id: str
    employee_id: str
    day: date
    timezone: str
    start: AwareDatetime
    end: AwareDatetime
    generated_at: AwareDatetime
    basis: Literal["declaration_recorded_at"] = "declaration_recorded_at"
    page: MatrixPage
    rows: list[DayRow]
    counts: dict[str, int]
    complete_attribution: Literal[False] = False
    conversion_basis_points: None = None


def read(db, institute, employee, day, limit=20, offset=0):
    lock_institute(db, institute); require_employee(db, institute, employee)
    start, end = day_bounds(db, institute, day); now = utcnow()
    try: zone = ZoneInfo(db.get(Institute, institute).timezone).key
    except (ZoneInfoNotFoundError, ValueError): zone = "UTC"
    own = (Original.institute_id == institute, Original.employee_id == employee,
           Original.created_at >= start, Original.created_at < end, false() if end <= start else Original.id.is_not(None))
    def joined(query):
        return query.select_from(Original).outerjoin(Cancellation,
            (Cancellation.institute_id == Original.institute_id) & (Cancellation.rebooking_id == Original.id)).outerjoin(Appointment,
            (Appointment.institute_id == Original.institute_id) & (Appointment.id == Original.target_appointment_id)).where(*own)
    counts = dict.fromkeys(STATES, 0)
    facts = joined(select(Original.created_at, Original.source_capture, Original.booking_capture, Cancellation.id,
        Appointment.status, Appointment.customer_id, Appointment.actual_start_time, Appointment.actual_end_time))
    for values in db.execute(facts.execution_options(yield_per=100)):
        counts[classify(*values, now)] += 1
    total = sum(counts.values())
    rows = db.execute(joined(select(Original, Cancellation, Appointment.status, Appointment.customer_id,
        Appointment.actual_start_time, Appointment.actual_end_time))
        .order_by(Original.created_at.desc(), Original.id).offset(offset).limit(limit))
    result = []
    for row, cancelled, status, customer, first, last in rows:
        key = classify(row.created_at, row.source_capture, row.booking_capture, cancelled.id if cancelled else None,
            status, customer, first, last, now)
        result.append(DayRow(original=dto(row, cancelled), target_status=status, target_customer_id=customer,
            actual_start=explicit_utc_instant(first), actual_end=explicit_utc_instant(last), state=key))
    return RebookingDay(institute_id=institute, employee_id=employee, day=day, timezone=zone, start=start, end=end,
        generated_at=now, page=MatrixPage(offset=offset, limit=limit, total=total), counts=counts, rows=result)


def classify(recorded, source, booking, cancelled, status, customer, first, last, now):
    if cancelled: return "cancelled_declaration"
    if explicit_utc_instant(recorded) > now: return "future_recording"
    source = ExecutionCapture.model_validate(source)
    booking = BookingCapture.model_validate(booking)
    if not customer or customer != source.customer_id: return "unknown_target"
    if status == "cancelled": return "cancelled_booking"
    if status == "no_show": return "no_show"
    if status in {"scheduled", "confirmed", "arrived", "in_progress"}: return "booked_return"
    first, last = explicit_utc_instant(first), explicit_utc_instant(last)
    if status == "completed" and first is not None and last is not None and last > first and last <= now \
        and first >= booking.created_at and first > source.actual_end: return "completed_return"
    return "unknown_target"
