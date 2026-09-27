from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.modules.planning.models import ServiceSession
from app.modules.tickets.models import QueueTicket, TicketLine
from app.modules.tickets.repository import list_waiting_tickets
from app.modules.tickets.schemas import (
    ChiffresSummaryRead,
    QueueTicketRead,
    TicketAssign,
    TicketCheckoutStart,
    TicketCreate,
    TicketLineAdd,
    TicketLineRead,
    TicketPaymentComplete,
)
from app.modules.tickets.service import (
    add_checkout_ticket_line,
    assign_ticket,
    cancel_ticket,
    complete_payment,
    create_queue_ticket,
    get_chiffres_by_employee,
    remove_checkout_ticket_line,
    start_checkout,
)

router = APIRouter(prefix="/tickets", tags=["tickets"])

ACTIVE_SESSION_STATUSES = {"planned", "in_progress", "extended", "delayed"}


def _to_float(value):
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _line_status(db: Session, ticket: QueueTicket, line: TicketLine) -> str:
    """Statut d'une ligne dans un ticket à session unique.

    Le planning démarre le ticket complet, pas les lignes une par une.
    Une seule session peut donc représenter toutes les prestations du ticket.
    """
    if ticket.status == "in_progress" and line.performed_by_employee_id:
        return "in_progress"

    if ticket.status in {"ready_for_checkout", "in_checkout", "paid"} and line.performed_by_employee_id:
        return "completed"

    sessions = list(
        db.scalars(
            select(ServiceSession).where(ServiceSession.ticket_line_id == line.id)
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
        checkout_employee_id=ticket.checkout_employee_id,
        checkout_started_at=ticket.checkout_started_at,
        paid_employee_id=ticket.paid_employee_id,
        paid_at=ticket.paid_at,
        payment_method=ticket.payment_method,
        total_amount=_to_float(ticket.total_amount),
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
                performed_by_employee_id=line.performed_by_employee_id,
                status=_line_status(db, ticket, line),
            )
            for line in lines
        ],
    )


@router.get("/chiffres", response_model=ChiffresSummaryRead)
def get_chiffres(institute_id: str, db: Session = Depends(get_db)) -> ChiffresSummaryRead:
    return get_chiffres_by_employee(db, institute_id)


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


@router.patch("/{ticket_id}/checkout/start", response_model=QueueTicketRead)
def patch_start_checkout(
    ticket_id: str,
    payload: TicketCheckoutStart,
    db: Session = Depends(get_db),
) -> QueueTicketRead:
    ticket = start_checkout(db, ticket_id, payload.employee_id)
    return _read_ticket(db, ticket)


@router.patch("/{ticket_id}/checkout/lines/add", response_model=QueueTicketRead)
def patch_add_checkout_line(
    ticket_id: str,
    payload: TicketLineAdd,
    db: Session = Depends(get_db),
) -> QueueTicketRead:
    ticket = add_checkout_ticket_line(db, ticket_id, payload.service_id)
    return _read_ticket(db, ticket)


@router.patch("/{ticket_id}/checkout/lines/{line_id}/remove", response_model=QueueTicketRead)
def patch_remove_checkout_line(
    ticket_id: str,
    line_id: str,
    db: Session = Depends(get_db),
) -> QueueTicketRead:
    ticket = remove_checkout_ticket_line(db, ticket_id, line_id)
    return _read_ticket(db, ticket)


@router.patch("/{ticket_id}/checkout/pay", response_model=QueueTicketRead)
def patch_complete_payment(
    ticket_id: str,
    payload: TicketPaymentComplete,
    db: Session = Depends(get_db),
) -> QueueTicketRead:
    ticket = complete_payment(db, ticket_id, payload.employee_id, payload.payment_method)
    return _read_ticket(db, ticket)
