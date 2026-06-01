from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.modules.planning.models import ServiceSession
from app.modules.tickets.models import QueueTicket, TicketLine
from app.modules.tickets.repository import list_waiting_tickets
from app.modules.tickets.schemas import QueueTicketRead, TicketAssign, TicketCreate, TicketLineRead
from app.modules.tickets.service import assign_ticket, cancel_ticket, create_queue_ticket

router = APIRouter(prefix="/tickets", tags=["tickets"])

ACTIVE_SESSION_STATUSES = {"planned", "in_progress", "extended", "delayed"}


def _to_float(value):
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _line_status(db: Session, line_id: str) -> str:
    sessions = list(
        db.scalars(
            select(ServiceSession).where(ServiceSession.ticket_line_id == line_id)
        ).all()
    )
    if any(session.status in ACTIVE_SESSION_STATUSES for session in sessions):
        return "in_progress"
    if any(session.status == "completed" for session in sessions):
        return "completed"
    return "pending"


def _read_ticket(db: Session, ticket: QueueTicket) -> QueueTicketRead:
    lines = list(
        db.scalars(
            select(TicketLine)
            .where(TicketLine.ticket_id == ticket.id)
            .order_by(TicketLine.id)
        ).all()
    )

    return QueueTicketRead(
        id=ticket.id,
        institute_id=ticket.institute_id,
        ticket_number=ticket.ticket_number,
        customer_id=ticket.customer_id,
        subscription_id=ticket.subscription_id,
        status=ticket.status,
        arrival_time=ticket.arrival_time,
        estimated_start_time=ticket.estimated_start_time,
        assigned_employee_id=ticket.assigned_employee_id,
        created_by_id=ticket.created_by_id,
        lines=[
            TicketLineRead(
                id=line.id,
                ticket_id=line.ticket_id,
                service_id=line.service_id,
                quantity=line.quantity,
                unit_price=_to_float(line.unit_price),
                total=_to_float(line.total),
                duration_minutes=line.duration_minutes,
                revenue_category=line.revenue_category,
                status=_line_status(db, line.id),
            )
            for line in lines
        ],
    )


@router.get("/waiting", response_model=list[QueueTicketRead])
def get_waiting_tickets(institute_id: str, db: Session = Depends(get_db)) -> list[QueueTicketRead]:
    return [_read_ticket(db, ticket) for ticket in list_waiting_tickets(db, institute_id)]


@router.post("", response_model=QueueTicketRead)
def post_ticket(payload: TicketCreate, db: Session = Depends(get_db)) -> QueueTicketRead:
    ticket = create_queue_ticket(db, payload)
    return _read_ticket(db, ticket)


@router.patch("/{ticket_id}/assign", response_model=QueueTicketRead)
def patch_assign_ticket(ticket_id: str, payload: TicketAssign, db: Session = Depends(get_db)) -> QueueTicketRead:
    ticket = assign_ticket(db, ticket_id, payload.employee_id)
    return _read_ticket(db, ticket)


@router.patch("/{ticket_id}/cancel", response_model=QueueTicketRead)
def patch_cancel_ticket(ticket_id: str, db: Session = Depends(get_db)) -> QueueTicketRead:
    ticket = cancel_ticket(db, ticket_id)
    return _read_ticket(db, ticket)
