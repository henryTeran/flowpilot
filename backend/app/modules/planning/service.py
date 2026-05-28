from datetime import datetime, timedelta, timezone
from math import ceil

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.employees.repository import get_employee, list_by_institute
from app.modules.planning.models import ServiceSession
from app.modules.planning.repository import get_session, list_sessions_for_day
from app.modules.planning.schemas import (
    AvailabilityEmployeeRead,
    PlanningAvailabilityRead,
    PlanningDayRead,
    PlanningEmployeeRow,
)
from app.modules.services.repository import get_service
from app.modules.tickets.models import QueueTicket, TicketLine
from app.modules.tickets.repository import get_ticket
from app.shared.exceptions import business_error, not_found
from app.shared.ids import new_id
from app.shared.time import utcnow


ACTIVE_SESSION_STATUSES = ["planned", "in_progress", "extended", "delayed"]
UNAVAILABLE_EMPLOYEE_STATUSES = {"pause", "absent", "offline"}


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _minutes_until(target: datetime | None, now: datetime) -> int | None:
    if target is None:
        return None
    return max(0, ceil((_ensure_aware(target) - now).total_seconds() / 60))


def _is_session_late(session: ServiceSession, now: datetime) -> bool:
    return (
        session.status in ACTIVE_SESSION_STATUSES
        and _ensure_aware(session.planned_end_time) <= now
    )


def _get_active_employee_session(
    db: Session,
    institute_id: str,
    employee_id: str,
    exclude_ticket_line_id: str | None = None,
) -> ServiceSession | None:
    """
    Retourne une session active pour une collaboratrice.

    Important : on ne filtre PAS avec planned_end_time > now.
    Une prestation en retard reste active tant qu'elle n'a pas été terminée.
    Sinon l'app considère à tort la collaboratrice comme disponible.
    """
    conditions = [
        ServiceSession.institute_id == institute_id,
        ServiceSession.employee_id == employee_id,
        ServiceSession.status.in_(ACTIVE_SESSION_STATUSES),
    ]

    if exclude_ticket_line_id:
        conditions.append(ServiceSession.ticket_line_id != exclude_ticket_line_id)

    return db.scalars(
        select(ServiceSession)
        .where(*conditions)
        .order_by(ServiceSession.planned_end_time.desc())
    ).first()


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


def get_institute_availability(db: Session, institute_id: str) -> PlanningAvailabilityRead:
    """
    Calcule la prochaine disponibilité visible par l'accueil.

    Règle métier corrigée :
    - une session en retard reste occupante ;
    - la collaboratrice ne redevient disponible qu'après action Fin ;
    - une session dépassée ne doit jamais afficher "disponible maintenant".
    """
    now = utcnow()
    employees = list_by_institute(db, institute_id)
    sessions = [
        session
        for session in list_sessions_for_day(db, institute_id, now)
        if session.status in ACTIVE_SESSION_STATUSES
    ]

    active_sessions_by_employee: dict[str, list[ServiceSession]] = {}
    for session in sessions:
        active_sessions_by_employee.setdefault(session.employee_id, []).append(session)

    rows: list[AvailabilityEmployeeRead] = []
    for employee in employees:
        employee_sessions = active_sessions_by_employee.get(employee.id, [])
        active_session = max(
            employee_sessions,
            key=lambda session: _ensure_aware(session.planned_end_time),
            default=None,
        )

        is_late = bool(active_session and _is_session_late(active_session, now))

        if employee.status in UNAVAILABLE_EMPLOYEE_STATUSES:
            display_status = employee.status
            available_at = None
            wait_minutes = None
        elif active_session and is_late:
            # Prestation dépassée : disponibilité inconnue tant que l'action Fin n'est pas faite.
            display_status = "delayed"
            available_at = None
            wait_minutes = None
        elif active_session:
            display_status = employee.status if employee.status != "available" else "busy"
            available_at = _ensure_aware(active_session.planned_end_time)
            wait_minutes = _minutes_until(available_at, now)
        else:
            display_status = employee.status
            available_at = now if employee.status == "available" else None
            wait_minutes = _minutes_until(available_at, now)

        rows.append(
            AvailabilityEmployeeRead(
                employee_id=employee.id,
                employee_name=employee.first_name,
                employee_status=display_status,
                available_at=available_at,
                wait_minutes=wait_minutes,
                active_session_id=active_session.id if active_session else None,
            )
        )

    available_rows = [row for row in rows if row.available_at is not None]
    next_row = min(available_rows, key=lambda row: _ensure_aware(row.available_at)) if available_rows else None

    waiting_tickets_count = db.scalars(
        select(QueueTicket).where(
            QueueTicket.institute_id == institute_id,
            QueueTicket.status.in_(["waiting", "assigned"]),
        )
    ).all()

    return PlanningAvailabilityRead(
        institute_id=institute_id,
        generated_at=now,
        next_employee_id=next_row.employee_id if next_row else None,
        next_employee_name=next_row.employee_name if next_row else None,
        next_available_at=next_row.available_at if next_row else None,
        wait_minutes=next_row.wait_minutes if next_row else None,
        active_sessions=len(sessions),
        waiting_tickets=len(waiting_tickets_count),
        employees=sorted(rows, key=lambda row: row.wait_minutes if row.wait_minutes is not None else 10_000),
    )


def start_service_session(db: Session, ticket_id: str, employee_id: str, service_id: str) -> ServiceSession:
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

    if ticket.status not in {"waiting", "assigned"}:
        raise business_error("Ce ticket est déjà en cours, terminé ou annulé")

    if ticket.assigned_employee_id and ticket.assigned_employee_id != employee.id:
        raise business_error("Ce ticket est déjà affecté à une autre collaboratrice")

    if employee.status != "available":
        raise business_error("Cette collaboratrice n'est pas disponible")

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
            raise business_error("Ce ticket possède déjà une prestation en cours")

    active_employee_session = _get_active_employee_session(
        db=db,
        institute_id=ticket.institute_id,
        employee_id=employee.id,
        exclude_ticket_line_id=line.id if line else None,
    )
    if active_employee_session:
        planned_end = _ensure_aware(active_employee_session.planned_end_time)
        now = utcnow()
        if planned_end <= now:
            raise business_error(
                f"{employee.first_name} a déjà une prestation en retard. Termine-la avant d'en démarrer une autre."
            )
        raise business_error(
            f"{employee.first_name} est déjà occupée jusqu’à {planned_end.strftime('%H:%M')}"
        )

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

    session.planned_end_time = _ensure_aware(session.planned_end_time) + timedelta(minutes=minutes)
    session.duration_minutes += minutes
    session.status = "extended"

    db.add(session)
    db.commit()
    db.refresh(session)
    return session
