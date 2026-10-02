from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.tickets.models import QueueTicket, TicketLine
from app.modules.tickets.domain import ACTIVE_TICKET_STATUSES, QUEUE_STATUSES
from app.modules.institutes.models import Institute
from app.shared.exceptions import not_found


def lock_institute(db: Session, institute_id: str) -> None:
    # Serialize operational mutations within an institute on PostgreSQL. Read
    # fresh aggregate state AFTER acquiring this lock (not from the identity map).
    institute = db.scalar(select(Institute).where(Institute.id == institute_id).with_for_update())
    if institute is None:
        raise not_found("Institut introuvable")


def lock_ticket(db: Session, ticket_id: str) -> QueueTicket:
    ticket = get_ticket(db, ticket_id)
    if ticket is None:
        raise not_found("Ticket introuvable")
    lock_institute(db, ticket.institute_id)
    db.refresh(ticket)
    return ticket


def queue_positions(db: Session, institute_id: str) -> dict[str, int]:
    ids = db.scalars(select(QueueTicket.id).where(
        QueueTicket.institute_id == institute_id,
        QueueTicket.status.in_(QUEUE_STATUSES),
    ).order_by(QueueTicket.arrival_time, QueueTicket.id)).all()
    return {ticket_id: index for index, ticket_id in enumerate(ids, start=1)}


def list_waiting_tickets(db: Session, institute_id: str) -> list[QueueTicket]:
    """Retourne les tickets visibles dans le flux opérationnel.

    Le nom est conservé pour compatibilité avec les routes existantes, mais la
    liste contient aussi les tickets en caisse depuis le pivot métier.
    """
    return list(
        db.scalars(
            select(QueueTicket)
            .where(
                QueueTicket.institute_id == institute_id,
                QueueTicket.status.in_(ACTIVE_TICKET_STATUSES),
            )
            .order_by(QueueTicket.arrival_time, QueueTicket.id)
        ).all()
    )


def count_today_tickets(db: Session, institute_id: str) -> int:
    return len(list_waiting_tickets(db, institute_id))


def get_ticket(db: Session, ticket_id: str) -> QueueTicket | None:
    return db.get(QueueTicket, ticket_id)


def get_ticket_by_idempotency_key(db: Session, institute_id: str, idempotency_key: str) -> QueueTicket | None:
    return db.scalars(
        select(QueueTicket).where(
            QueueTicket.institute_id == institute_id,
            QueueTicket.idempotency_key == idempotency_key,
        )
    ).first()


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
