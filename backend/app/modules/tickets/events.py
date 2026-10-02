"""Store lifecycle facts in the same transaction as the ticket mutation."""
from sqlalchemy.orm import Session

from app.modules.tickets.domain import validate_transition
from app.modules.tickets.models import QueueEvent, QueueTicket
from app.shared.time import utcnow


def record_event(db: Session, ticket: QueueTicket, event_type: str,
                 previous_status: str | None, employee_id: str | None = None) -> None:
    db.add(QueueEvent(
        institute_id=ticket.institute_id, ticket_id=ticket.id,
        event_type=event_type, previous_status=previous_status,
        status=ticket.status, employee_id=employee_id, occurred_at=utcnow(),
    ))


def transition_ticket(db: Session, ticket: QueueTicket, next_status: str,
                      event_type: str, employee_id: str | None = None) -> None:
    previous = ticket.status
    validate_transition(previous, next_status)
    ticket.status = next_status
    record_event(db, ticket, event_type, previous, employee_id)
