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
PAYMENT_METHODS = {"cb", "especes", "cheque", "carte_cadeau", "mixte"}


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


def _ticket_lines(db: Session, ticket_id: str) -> list[TicketLine]:
    return list(
        db.scalars(
            select(TicketLine)
            .where(TicketLine.ticket_id == ticket_id)
            .order_by(TicketLine.id)
        ).all()
    )


def _ticket_total(db: Session, ticket_id: str) -> float:
    total = 0.0
    for line in _ticket_lines(db, ticket_id):
        if line.total is not None:
            total += float(line.total)
    return total


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
    total_amount = sum(float(service.price_passage or 0) for service in services)
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
        total_amount=total_amount,
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
        raise business_error("Ce ticket est déjà en prestation, en caisse, payé ou annulé")

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

    if ticket.status in {"paid", "completed"}:
        raise business_error("Ce ticket est déjà payé")

    if ticket.status == "in_progress":
        raise business_error("Ce ticket est en cours : termine d'abord la prestation depuis le planning")

    if ticket.status not in {"waiting", "assigned", "ready_for_checkout", "in_checkout"}:
        raise business_error("Ce ticket ne peut pas être annulé dans son état actuel")

    ticket.status = "cancelled"
    ticket.assigned_employee_id = None
    ticket.estimated_start_time = None
    return save_ticket(db, ticket)


def start_checkout(db: Session, ticket_id: str, employee_id: str) -> QueueTicket:
    """Démarre l'encaissement après ré-identification collaboratrice.

    Règle BodyMinute : la personne qui a créé le ticket n'est pas forcément celle
    qui encaisse. L'encaissement doit donc enregistrer une nouvelle identité.
    """
    ticket = get_ticket(db, ticket_id)
    if not ticket:
        raise not_found("Ticket introuvable")

    employee = get_employee(db, employee_id)
    if not employee:
        raise not_found("Collaboratrice introuvable")
    if employee.institute_id != ticket.institute_id:
        raise business_error("La collaboratrice ne fait pas partie de cet institut")

    if ticket.status not in {"ready_for_checkout", "in_checkout"}:
        raise business_error("Le ticket doit être prêt pour la caisse avant encaissement")

    if ticket.status == "in_checkout" and ticket.checkout_employee_id and ticket.checkout_employee_id != employee.id:
        raise business_error("Ce ticket est déjà ouvert en caisse par une autre collaboratrice")

    ticket.status = "in_checkout"
    ticket.checkout_employee_id = employee.id
    ticket.checkout_started_at = ticket.checkout_started_at or utcnow()
    ticket.total_amount = _ticket_total(db, ticket.id)
    return save_ticket(db, ticket)


def complete_payment(db: Session, ticket_id: str, employee_id: str, payment_method: str) -> QueueTicket:
    ticket = get_ticket(db, ticket_id)
    if not ticket:
        raise not_found("Ticket introuvable")

    employee = get_employee(db, employee_id)
    if not employee:
        raise not_found("Collaboratrice introuvable")
    if employee.institute_id != ticket.institute_id:
        raise business_error("La collaboratrice ne fait pas partie de cet institut")

    if payment_method not in PAYMENT_METHODS:
        raise business_error("Mode de paiement invalide")

    if ticket.status not in {"ready_for_checkout", "in_checkout"}:
        raise business_error("Ce ticket ne peut pas être payé dans son état actuel")

    if ticket.checkout_employee_id and ticket.checkout_employee_id != employee.id:
        raise business_error("La collaboratrice identifiée en caisse doit valider le paiement")

    # Filet de sécurité : si une ligne n'a pas encore d'exécutante, on l'attribue
    # à la collaboratrice qui encaisse. Dans le flux normal, elle est déjà remplie
    # au démarrage de la prestation.
    for line in _ticket_lines(db, ticket.id):
        if not line.performed_by_employee_id:
            line.performed_by_employee_id = employee.id
            db.add(line)

    ticket.status = "paid"
    ticket.checkout_employee_id = ticket.checkout_employee_id or employee.id
    ticket.checkout_started_at = ticket.checkout_started_at or utcnow()
    ticket.paid_employee_id = employee.id
    ticket.paid_at = utcnow()
    ticket.payment_method = payment_method
    ticket.total_amount = _ticket_total(db, ticket.id)

    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket
