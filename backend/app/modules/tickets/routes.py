from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.modules.tickets.repository import list_waiting_tickets
from app.modules.tickets.schemas import QueueTicketRead, TicketAssign, TicketCreate
from app.modules.tickets.service import assign_ticket, cancel_ticket, create_queue_ticket

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.get("/waiting", response_model=list[QueueTicketRead])
def get_waiting_tickets(institute_id: str, db: Session = Depends(get_db)) -> list[QueueTicketRead]:
    return list_waiting_tickets(db, institute_id)


@router.post("", response_model=QueueTicketRead)
def post_ticket(payload: TicketCreate, db: Session = Depends(get_db)) -> QueueTicketRead:
    return create_queue_ticket(db, payload)


@router.patch("/{ticket_id}/assign", response_model=QueueTicketRead)
def patch_assign_ticket(ticket_id: str, payload: TicketAssign, db: Session = Depends(get_db)) -> QueueTicketRead:
    return assign_ticket(db, ticket_id, payload.employee_id)


@router.patch("/{ticket_id}/cancel", response_model=QueueTicketRead)
def patch_cancel_ticket(ticket_id: str, db: Session = Depends(get_db)) -> QueueTicketRead:
    return cancel_ticket(db, ticket_id)
