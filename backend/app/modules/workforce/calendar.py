from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from sqlalchemy import DateTime, String, case, cast, func, literal, select, union_all
from app.modules.employees.models import Employee
from app.modules.institutes.models import Institute
from app.modules.institutes.calendar import day_bounds
from app.modules.appointments.models import Appointment
from app.modules.planning.models import ServiceSession
from app.modules.resources.repository import skill_facts
from app.modules.services.models import Service
from app.modules.scheduling.repository import ACTIVE_SESSION_STATUSES
from app.modules.scheduling.service import availability_engine
from app.modules.tickets.repository import lock_institute
from app.modules.workforce.models import EmployeeAbsence, AbsenceCancellation
from app.shared.exceptions import not_found
from app.shared.time import utcnow


def events_statement(institute, employee, start, end):
    def text_null():
        return cast(literal(None), String)

    def time_null():
        return cast(literal(None), DateTime(timezone=True))

    booked_start = func.coalesce(Appointment.booked_start_time, Appointment.start_time)
    booked_end = func.coalesce(Appointment.booked_end_time, Appointment.end_time)
    appointment_overlap = ((booked_start < end) & (booked_end > start)) | (
        (Appointment.actual_start_time < end) & ((Appointment.actual_end_time > start)
        | ((Appointment.actual_end_time.is_(None)) & (Appointment.status == "in_progress"))))
    appointments = select(literal("appointment").label("source_kind"), Appointment.id, Appointment.status,
        Appointment.service_id, booked_start.label("start_time"), booked_end.label("end_time"),
        Appointment.actual_start_time, Appointment.actual_end_time,
        text_null().label("absence_kind"), text_null().label("reason"), text_null().label("cancellation_id")
    ).where(Appointment.institute_id == institute, Appointment.employee_id == employee, start < end, appointment_overlap)
    session_overlap = (ServiceSession.start_time < end) & (
        (ServiceSession.planned_end_time > start) | (ServiceSession.real_end_time > start)
        | ((ServiceSession.real_end_time.is_(None)) & ServiceSession.status.in_(ACTIVE_SESSION_STATUSES)))
    sessions = select(literal("session"), ServiceSession.id, ServiceSession.status, ServiceSession.service_id,
        ServiceSession.start_time, ServiceSession.planned_end_time,
        case((ServiceSession.status != "planned", ServiceSession.start_time), else_=time_null()),
        ServiceSession.real_end_time, text_null(), text_null(), text_null()
    ).where(ServiceSession.institute_id == institute, ServiceSession.employee_id == employee, start < end, session_overlap)
    absences = select(literal("absence"), EmployeeAbsence.id,
        case((AbsenceCancellation.id.is_not(None), literal("cancelled")), else_=literal("recorded")),
        text_null(), EmployeeAbsence.start_time, EmployeeAbsence.end_time, time_null(), time_null(),
        EmployeeAbsence.kind, EmployeeAbsence.reason, AbsenceCancellation.id
    ).outerjoin(AbsenceCancellation, (AbsenceCancellation.institute_id == EmployeeAbsence.institute_id)
        & (AbsenceCancellation.absence_id == EmployeeAbsence.id)
    ).where(EmployeeAbsence.institute_id == institute, EmployeeAbsence.employee_id == employee, start < end,
            EmployeeAbsence.start_time < end, EmployeeAbsence.end_time > start)
    return union_all(appointments, sessions, absences).subquery("employee_calendar_events")


def read_employee_day(db, institute, employee, day, limit=50, offset=0):
    # The same institute lock protects source counts/page, current skills and
    # availability against operational mutations. Session close releases it.
    lock_institute(db, institute)
    row = db.scalar(select(Employee).where(Employee.institute_id == institute, Employee.id == employee))
    if row is None:
        raise not_found("Collaboratrice introuvable")
    start, end = day_bounds(db, institute, day)
    zone = db.get(Institute, institute).timezone
    try:
        ZoneInfo(zone)
    except (ZoneInfoNotFoundError, ValueError):
        zone = "UTC"
    now = utcnow()
    source = events_statement(institute, employee, start, end)
    total = db.scalar(select(func.count()).select_from(source))
    events = list(db.execute(select(source, Service.name.label("service_name"))
                            .outerjoin(Service, Service.id == source.c.service_id)
                            .order_by(source.c.start_time, source.c.source_kind, source.c.id)
                            .limit(limit).offset(offset)).mappings())
    return {"institute_id": institute, "generated_at": now, "day": day, "timezone": zone,
        "day_start": start, "day_end": end,
        "employee": {"id": row.id, "first_name": row.first_name, "status": row.status,
                     "skills": sorted(skill_facts(db, institute, [employee])[employee])},
        "availability": availability_engine(db, institute, employee, now=now),
        "event_page": {"offset": offset, "limit": limit, "total": total}, "events": events}
