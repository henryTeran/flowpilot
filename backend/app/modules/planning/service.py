from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.employees.repository import get_employee, list_by_institute
from app.modules.planning.models import ServiceSession
from app.modules.planning.repository import get_session, list_sessions_for_day
from app.modules.planning.schemas import PlanningDayRead, PlanningEmployeeRow
from app.modules.services.repository import get_service
from app.modules.tickets.models import TicketLine
from app.modules.tickets.repository import get_ticket
from app.shared.exceptions import business_error, not_found
from app.shared.ids import new_id
from app.shared.time import utcnow


ACTIVE_SESSION_STATUSES = ["planned", "in_progress", "extended", "delayed"]


def get_day_planning(db: Session, institute_id: str) -> PlanningDayRead:
    employees = list_by_institute(db, institute_id)
    sessions = list_sessions_for_day(db, institute_id, utcnow())

    sessions_by_employee: dict[str, list[ServiceSession]] = {}
    for session in sessions:
        sessions_by_employee.setdefault(session.employee_id, []).append(session)

    rows = [
        PlanningEmployeeRow(
            employee_id=employee.id,
            employee_name=employee.first_name,
            employee_status=employee.status,
            sessions=sessions_by_employee.get(employee.id, []),
        )
        for employee in employees
    ]
    return PlanningDayRead(institute_id=institute_id, generated_at=utcnow(), rows=rows)


def start_service_session(db: Session, ticket_id: str, employee_id: str, service_id: str) -> ServiceSession:
    """
    Démarre une prestation en évitant les commits partiels.

    Avant correction, le ticket pouvait passer en in_progress et la collaboratrice en busy
    avant que la session planning ne soit réellement créée. Résultat : la file semblait
    correcte, mais le bloc horaire n'apparaissait pas dans le planning.
    """
    ticket = get_ticket(db, ticket_id)
    if not ticket:
        raise not_found("Ticket introuvable")

    employee = get_employee(db, employee_id)
    if not employee:
        raise not_found("Collaboratrice introuvable")

    service = get_service(db, service_id)
    if not service:
        raise not_found("Prestation introuvable")

    if employee.institute_id != ticket.institute_id:
        raise business_error("Collaboratrice hors institut")

    line = db.scalars(
        select(TicketLine).where(
            TicketLine.ticket_id == ticket.id,
            TicketLine.service_id == service.id,
        )
    ).first()

    if line:
        existing_session = db.scalars(
            select(ServiceSession).where(
                ServiceSession.ticket_line_id == line.id,
                ServiceSession.status.in_(ACTIVE_SESSION_STATUSES),
            )
        ).first()
        if existing_session:
            return existing_session

    now = utcnow()
    session = ServiceSession(
        id=new_id("sess"),
        ticket_line_id=line.id if line else None,
        institute_id=ticket.institute_id,
        employee_id=employee.id,
        service_id=service.id,
        start_time=now,
        planned_end_time=now + timedelta(minutes=service.duration_min),
        duration_minutes=service.duration_min,
        status="in_progress",
    )

    ticket.status = "in_progress"
    ticket.assigned_employee_id = employee.id
    employee.status = "busy"

    db.add(ticket)
    db.add(employee)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def finish_service_session(db: Session, session_id: str) -> ServiceSession:
    session = get_session(db, session_id)
    if not session:
        raise not_found("Session introuvable")

    session.real_end_time = utcnow()
    session.status = "completed"

    employee = get_employee(db, session.employee_id)
    if employee:
        employee.status = "available"
        db.add(employee)

    if session.ticket_line_id:
        line = db.get(TicketLine, session.ticket_line_id)
        if line:
            ticket = get_ticket(db, line.ticket_id)
            if ticket:
                ticket.status = "completed"
                db.add(ticket)

    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def extend_service_session(db: Session, session_id: str, minutes: int) -> ServiceSession:
    if minutes not in {5, 10, 15, 20, 30, 45, 60}:
        raise business_error("Prolongation autorisée : 5, 10, 15, 20, 30, 45 ou 60 minutes")

    session = get_session(db, session_id)
    if not session:
        raise not_found("Session introuvable")

    session.planned_end_time = session.planned_end_time + timedelta(minutes=minutes)
    session.duration_minutes += minutes
    session.status = "extended"

    db.add(session)
    db.commit()
    db.refresh(session)
    return session
