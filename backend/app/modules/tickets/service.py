from datetime import timedelta

from sqlalchemy.orm import Session

from app.modules.employees.repository import get_employee, list_by_institute
from app.modules.services.repository import get_service
from app.modules.tickets.models import QueueTicket, TicketLine
from app.modules.tickets.repository import get_ticket, list_waiting_tickets, save_ticket, save_ticket_line
from app.modules.tickets.schemas import TicketCreate
from app.shared.exceptions import business_error, not_found
from app.shared.ids import new_id
from app.shared.time import utcnow


def _generate_ticket_number(db: Session, institute_id: str) -> str:
    count = len(list_waiting_tickets(db, institute_id)) + 1
    return f"T-{count:03d}"


def estimate_start_time(db: Session, institute_id: str, service_duration_minutes: int):
    available_employees = [
        employee for employee in list_by_institute(db, institute_id)
        if employee.status in {"available", "busy"}
    ]
    now = utcnow()
    if not available_employees:
        return now + timedelta(minutes=service_duration_minutes)

    active_tickets = list_waiting_tickets(db, institute_id)
    workload_minutes = len(active_tickets) * service_duration_minutes
    wait_minutes = workload_minutes // max(len(available_employees), 1)
    return now + timedelta(minutes=wait_minutes)


def create_queue_ticket(db: Session, payload: TicketCreate) -> QueueTicket:
    service = get_service(db, payload.service_id)
    if not service:
        raise not_found("Prestation introuvable")

    now = utcnow()
    ticket = QueueTicket(
        id=new_id("qt"),
        institute_id=payload.institute_id,
        ticket_number=_generate_ticket_number(db, payload.institute_id),
        customer_id=payload.customer_id,
        subscription_id=payload.subscription_id,
        status="waiting",
        arrival_time=now,
        estimated_start_time=estimate_start_time(db, payload.institute_id, service.duration_min),
        created_by_id=payload.created_by_id,
    )
    saved = save_ticket(db, ticket)

    line = TicketLine(
        id=new_id("tl"),
        ticket_id=saved.id,
        service_id=service.id,
        quantity=1,
        unit_price=service.price_passage,
        total=service.price_passage,
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
    if employee.status not in {"available", "busy"}:
        raise business_error("La collaboratrice n'est pas disponible pour recevoir un ticket")

    ticket.status = "assigned"
    ticket.assigned_employee_id = employee.id
    return save_ticket(db, ticket)
