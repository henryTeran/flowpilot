from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.employees.repository import get_employee, list_by_institute
from app.modules.planning.models import ServiceSession
from app.modules.services.repository import get_service
from app.modules.tickets.models import QueueTicket, TicketLine
from app.modules.tickets.repository import get_ticket, list_waiting_tickets, save_ticket, save_ticket_line
from app.modules.tickets.schemas import TicketCreate
from app.shared.exceptions import business_error, not_found
from app.shared.ids import new_id
from app.shared.time import utcnow


ACTIVE_SESSION_STATUSES = ["planned", "in_progress", "extended", "delayed"]
ASSIGNABLE_EMPLOYEE_STATUSES = {"available"}


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _generate_ticket_number(db: Session, institute_id: str) -> str:
    count = len(list_waiting_tickets(db, institute_id)) + 1
    return f"T-{count:03d}"


def _first_line_duration(db: Session, ticket_id: str, fallback_minutes: int) -> int:
    line = db.scalars(select(TicketLine).where(TicketLine.ticket_id == ticket_id)).first()
    return line.duration_minutes if line else fallback_minutes


def _payload_service_ids(payload: TicketCreate) -> list[str]:
    """Retourne les prestations du ticket en conservant la compatibilité service_id."""
    service_ids: list[str] = []
    if payload.service_ids:
        service_ids.extend(payload.service_ids)
    elif payload.service_id:
        service_ids.append(payload.service_id)

    # On supprime les valeurs vides, mais on garde les doublons éventuels si le métier
    # permet plus tard deux fois la même prestation dans un même ticket.
    return [service_id for service_id in service_ids if service_id]


def estimate_start_time(db: Session, institute_id: str, service_duration_minutes: int):
    """
    Estime le début du prochain ticket selon :
    - les collaboratrices disponibles ;
    - les sessions planning déjà en cours ;
    - les tickets encore en file d'attente.
    """
    now = utcnow()
    employees = [
        employee
        for employee in list_by_institute(db, institute_id)
        if employee.status in ASSIGNABLE_EMPLOYEE_STATUSES
    ]

    if not employees:
        return now + timedelta(minutes=service_duration_minutes)

    active_sessions = list(
        db.scalars(
            select(ServiceSession).where(
                ServiceSession.institute_id == institute_id,
                ServiceSession.status.in_(ACTIVE_SESSION_STATUSES),
            )
        ).all()
    )

    availability_by_employee: dict[str, datetime] = {}
    for employee in employees:
        employee_sessions = [session for session in active_sessions if session.employee_id == employee.id]
        if not employee_sessions:
            availability_by_employee[employee.id] = now
            continue

        latest_session = max(employee_sessions, key=lambda session: _ensure_aware(session.planned_end_time))
        planned_end = _ensure_aware(latest_session.planned_end_time)
        availability_by_employee[employee.id] = planned_end if planned_end > now else now

    queue = list(
        db.scalars(
            select(QueueTicket)
            .where(
                QueueTicket.institute_id == institute_id,
                QueueTicket.status.in_(["waiting", "assigned"]),
            )
            .order_by(QueueTicket.arrival_time)
        ).all()
    )

    for ticket in queue:
        employee_id = min(availability_by_employee, key=lambda item: availability_by_employee[item])
        duration = _first_line_duration(db, ticket.id, service_duration_minutes)
        availability_by_employee[employee_id] = availability_by_employee[employee_id] + timedelta(minutes=duration)

    return min(availability_by_employee.values())


def create_queue_ticket(db: Session, payload: TicketCreate) -> QueueTicket:
    service_ids = _payload_service_ids(payload)
    if not service_ids:
        raise business_error("Ajoute au moins une prestation au ticket")

    services = []
    for service_id in service_ids:
        service = get_service(db, service_id)
        if not service:
            raise not_found(f"Prestation introuvable : {service_id}")
        services.append(service)

    total_duration = sum(service.duration_min for service in services)
    now = utcnow()
    ticket = QueueTicket(
        id=new_id("qt"),
        institute_id=payload.institute_id,
        ticket_number=_generate_ticket_number(db, payload.institute_id),
        customer_id=payload.customer_id,
        subscription_id=payload.subscription_id,
        status="waiting",
        arrival_time=now,
        estimated_start_time=estimate_start_time(db, payload.institute_id, total_duration),
        created_by_id=payload.created_by_id,
    )
    saved = save_ticket(db, ticket)

    for service in services:
        unit_price = service.price_passage
        line = TicketLine(
            id=new_id("tl"),
            ticket_id=saved.id,
            service_id=service.id,
            quantity=1,
            unit_price=unit_price,
            total=unit_price,
            duration_minutes=service.duration_min,
            revenue_category="care",
        )
        save_ticket_line(db, line)

    return saved


def assign_ticket(db: Session, ticket_id: str, employee_id: str) -> QueueTicket:
    ticket = get_ticket(db, ticket_id)
    if not ticket:
        raise not_found("Ticket introuvable")
    employee = get_employee(db, employee_id)
    if not employee:
        raise not_found("Collaboratrice introuvable")
    if employee.institute_id != ticket.institute_id:
        raise business_error("La collaboratrice ne fait pas partie de cet institut")

    if ticket.status not in {"waiting", "assigned"}:
        raise business_error("Ce ticket est déjà en cours, terminé ou annulé")

    if ticket.status == "assigned" and ticket.assigned_employee_id and ticket.assigned_employee_id != employee.id:
        raise business_error("Ce ticket est déjà affecté à une autre collaboratrice")

    if employee.status not in ASSIGNABLE_EMPLOYEE_STATUSES:
        raise business_error("La collaboratrice n'est pas disponible pour recevoir un ticket")

    ticket.status = "assigned"
    ticket.assigned_employee_id = employee.id
    return save_ticket(db, ticket)


def cancel_ticket(db: Session, ticket_id: str) -> QueueTicket:
    ticket = get_ticket(db, ticket_id)
    if not ticket:
        raise not_found("Ticket introuvable")

    if ticket.status == "cancelled":
        return ticket

    if ticket.status == "completed":
        raise business_error("Ce ticket est déjà terminé")

    if ticket.status == "in_progress":
        raise business_error("Ce ticket est en cours : termine d'abord la prestation depuis le planning")

    if ticket.status not in {"waiting", "assigned"}:
        raise business_error("Ce ticket ne peut pas être annulé dans son état actuel")

    ticket.status = "cancelled"
    ticket.assigned_employee_id = None
    ticket.estimated_start_time = None
    return save_ticket(db, ticket)
