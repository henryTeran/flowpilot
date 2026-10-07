"""Bounded completed-execution choices; eligibility never creates attribution."""
from datetime import date
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pydantic import BaseModel, AwareDatetime
from fastapi import HTTPException
from sqlalchemy import select, union_all, literal, func, false
from app.modules.planning.models import ServiceSession
from app.modules.appointments.models import Appointment, BookingEvent
from app.modules.tickets.models import TicketLine, QueueTicket
from app.modules.customers.models import Customer
from app.modules.institutes.models import Institute
from app.modules.institutes.calendar import day_bounds
from app.modules.workforce.models import EmployeeRebooking, RebookingCancellation
from app.modules.workforce.objectives import require_employee
from app.modules.workforce.rebooking_sources import ExecutionCapture, BookingCapture, execution, capture_booking
from app.modules.workforce.schemas import MatrixPage
from app.modules.tickets.repository import lock_institute
from app.shared.time import utcnow, explicit_utc_instant


class SourceOption(BaseModel):
    kind: Literal["session", "appointment"]
    id: str
    service_id: str
    actual_start: AwareDatetime | None
    actual_end: AwareDatetime
    customer_id: str | None
    customer_known: bool
    already_attributed: bool
    exclusion: Literal["invalid_execution", "future_end", "unknown_customer", "already_attributed"] | None
    capture: ExecutionCapture | None


class SourceOptions(BaseModel):
    institute_id: str
    employee_id: str
    day: date
    timezone: str
    start: AwareDatetime
    end: AwareDatetime
    generated_at: AwareDatetime
    basis: Literal["actual_completion_day"] = "actual_completion_day"
    complete_sources: Literal[False] = False
    page: MatrixPage
    rows: list[SourceOption]


def read_sources(db, institute, employee, day, limit=20, offset=0):
    lock_institute(db, institute); require_employee(db, institute, employee)
    start, end = day_bounds(db, institute, day); now = utcnow()
    try: zone = ZoneInfo(db.get(Institute, institute).timezone).key
    except (ZoneInfoNotFoundError, ValueError): zone = "UTC"
    def active(column, identifier):
        return select(EmployeeRebooking.id).outerjoin(RebookingCancellation,
            (RebookingCancellation.institute_id == EmployeeRebooking.institute_id) & (RebookingCancellation.rebooking_id == EmployeeRebooking.id)) \
            .where(EmployeeRebooking.institute_id == institute, column == identifier, RebookingCancellation.id.is_(None)).exists()
    def known(identifier):
        return select(Customer.id).where(Customer.institute_id == institute, Customer.id == identifier).exists()
    session = select(literal("session").label("kind"), ServiceSession.id.label("id"), ServiceSession.service_id.label("service_id"),
        ServiceSession.start_time.label("first"), ServiceSession.real_end_time.label("last"), QueueTicket.customer_id.label("customer_id"),
        known(QueueTicket.customer_id).label("known"), active(EmployeeRebooking.session_id, ServiceSession.id).label("attributed")) \
        .select_from(ServiceSession).outerjoin(TicketLine, TicketLine.id == ServiceSession.ticket_line_id).outerjoin(QueueTicket,
            (QueueTicket.id == TicketLine.ticket_id) & (QueueTicket.institute_id == institute)) \
        .where(ServiceSession.institute_id == institute, ServiceSession.employee_id == employee, ServiceSession.status == "completed",
            ServiceSession.real_end_time >= start, ServiceSession.real_end_time < end)
    appointment = select(literal("appointment"), Appointment.id, Appointment.service_id, Appointment.actual_start_time, Appointment.actual_end_time,
        Appointment.customer_id, known(Appointment.customer_id), active(EmployeeRebooking.source_appointment_id, Appointment.id)) \
        .where(Appointment.institute_id == institute, Appointment.employee_id == employee, Appointment.status == "completed",
            Appointment.actual_end_time >= start, Appointment.actual_end_time < end)
    sources = union_all(session, appointment).subquery()
    predicate = false() if end <= start else sources.c.id.is_not(None)
    total = db.scalar(select(func.count()).select_from(sources).where(predicate))
    rows = db.execute(select(sources).where(predicate).order_by(sources.c.last.desc(), sources.c.kind, sources.c.id).offset(offset).limit(limit)).mappings()
    result = []
    for row in rows:
        first, last = explicit_utc_instant(row["first"]), explicit_utc_instant(row["last"])
        why = "invalid_execution" if first is None or last <= first else "future_end" if last > now \
            else "unknown_customer" if not row["known"] else "already_attributed" if row["attributed"] else None
        capture = ExecutionCapture(kind=row["kind"], id=row["id"], employee_id=employee, service_id=row["service_id"],
            customer_id=row["customer_id"], actual_start=first, actual_end=last) if why is None else None
        result.append(SourceOption(kind=row["kind"], id=row["id"], service_id=row["service_id"], actual_start=first, actual_end=last,
            customer_id=row["customer_id"], customer_known=row["known"], already_attributed=row["attributed"], exclusion=why, capture=capture))
    return SourceOptions(institute_id=institute, employee_id=employee, day=day, timezone=zone, start=start, end=end,
        generated_at=now, page=MatrixPage(offset=offset, limit=limit, total=total), rows=result)


class TargetOption(BaseModel):
    id: str
    employee_id: str
    service_id: str
    status: str
    customer_id: str
    booked_start: AwareDatetime | None
    booked_end: AwareDatetime | None
    creation_events: int
    already_attributed: bool
    exclusion: Literal["already_attributed", "invalid_booking"] | None
    capture: BookingCapture | None


class TargetOptions(BaseModel):
    institute_id: str
    generated_at: AwareDatetime
    source: ExecutionCapture
    page: MatrixPage
    rows: list[TargetOption]


def read_targets(db, institute, kind, identifier, limit=20, offset=0):
    lock_institute(db, institute); now = utcnow()
    source = execution(db, institute, kind, identifier, now)
    # All current active appointments for this exact explicit client are visible;
    # prior/legacy appointments remain disabled rather than gaining fake dates.
    own = (Appointment.institute_id == institute, Appointment.customer_id == source.customer_id,
           Appointment.status.in_(["scheduled", "confirmed", "arrived", "in_progress", "completed"]))
    total = db.scalar(select(func.count()).select_from(Appointment).where(*own))
    events = select(BookingEvent.appointment_id.label("appointment"), func.count().label("count"), func.min(BookingEvent.id).label("id")) \
        .join(Appointment, (Appointment.id == BookingEvent.appointment_id) & (Appointment.institute_id == BookingEvent.institute_id)) \
        .where(BookingEvent.institute_id == institute, BookingEvent.event_type == "created", *own) \
        .group_by(BookingEvent.appointment_id).correlate(None).subquery()
    attributed = select(EmployeeRebooking.id).outerjoin(RebookingCancellation,
        (RebookingCancellation.institute_id == EmployeeRebooking.institute_id) & (RebookingCancellation.rebooking_id == EmployeeRebooking.id)) \
        .where(EmployeeRebooking.institute_id == institute, EmployeeRebooking.target_appointment_id == Appointment.id,
               RebookingCancellation.id.is_(None)).exists()
    rows = db.execute(select(Appointment, BookingEvent, events.c.count, attributed).outerjoin(events, events.c.appointment == Appointment.id)
        .outerjoin(BookingEvent, (BookingEvent.id == events.c.id) & (BookingEvent.institute_id == institute))
        .where(*own).order_by(Appointment.start_time.desc(), Appointment.id).offset(offset).limit(limit))
    result = []
    for target, event, count, linked in rows:
        count = count or 0; capture = None; why = "already_attributed" if linked else None
        if why is None:
            try: capture = capture_booking(target, [event]*min(count, 2), source, now)
            except HTTPException: why = "invalid_booking"
        result.append(TargetOption(id=target.id, employee_id=target.employee_id, service_id=target.service_id, status=target.status,
            customer_id=target.customer_id, booked_start=explicit_utc_instant(target.booked_start_time), booked_end=explicit_utc_instant(target.booked_end_time),
            creation_events=count, already_attributed=linked, exclusion=why, capture=capture))
    return TargetOptions(institute_id=institute, generated_at=now, source=source,
        page=MatrixPage(offset=offset, limit=limit, total=total), rows=result)
