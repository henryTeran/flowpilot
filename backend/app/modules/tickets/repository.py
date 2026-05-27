from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.tickets.models import QueueTicket, TicketLine


def list_waiting_tickets(db: Session, institute_id: str) -> list[QueueTicket]:
    return list(
        db.scalars(
            select(QueueTicket)
            .where(
                QueueTicket.institute_id == institute_id,
                QueueTicket.status.in_(["waiting", "assigned", "in_progress"]),
            )
            .order_by(QueueTicket.arrival_time)
        ).all()
    )


def count_today_tickets(db: Session, institute_id: str) -> int:
    return len(list_waiting_tickets(db, institute_id))


def get_ticket(db: Session, ticket_id: str) -> QueueTicket | None:
    return db.get(QueueTicket, ticket_id)


def save_ticket(db: Session, ticket: QueueTicket) -> QueueTicket:
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


def save_ticket_line(db: Session, line: TicketLine) -> TicketLine:
    db.add(line)
    db.commit()
    db.refresh(line)
    return line
