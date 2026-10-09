from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext
from hashlib import sha256
import json

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.appointments.models import Appointment
from app.modules.employees.repository import get_employee, list_by_institute
from app.modules.planning.models import ServiceSession
from app.modules.services.repository import get_service
from app.modules.tickets.models import QueueTicket, TicketLine
from app.modules.tickets.events import record_event, transition_ticket
from app.modules.tickets.repository import (
    get_ticket,
    get_ticket_by_idempotency_key,
    save_ticket,
    lock_institute,
    lock_ticket,
)
from app.modules.tickets.schemas import TicketCreate
from app.shared.exceptions import business_error, not_found
from app.shared.ids import new_id
from app.shared.time import utcnow


ACTIVE_SESSION_STATUSES = ["planned", "in_progress", "extended", "delayed"]


def read_operational_queue(db: Session, institute_id: str) -> list[dict]:
    """Minimal read projection using the existing operational queue ordering."""
    from app.modules.tickets.repository import list_waiting_tickets, queue_positions
    from app.shared.time import explicit_utc_instant
    positions = queue_positions(db, institute_id)
    return [{"ticket_id": ticket.id, "status": ticket.status,
             "arrival_time": explicit_utc_instant(ticket.arrival_time),
             "assigned_employee_id": ticket.assigned_employee_id,
             "queue_position": positions.get(ticket.id)}
            for ticket in list_waiting_tickets(db, institute_id)]
ACTIVE_APPOINTMENT_STATUSES = ["scheduled", "confirmed", "arrived", "in_progress"]
ASSIGNABLE_EMPLOYEE_STATUSES = {"available"}
PAYMENT_METHODS = {"cb", "especes", "cheque", "carte_cadeau", "mixte"}


def attach_checkout_customer(db: Session, ticket_id: str, customer_id: str | None) -> QueueTicket:
    from app.modules.customers.repository import require_customer
    from app.modules.commerce.models import PackageRedemption

    ticket = lock_ticket(db, ticket_id)
    if ticket.status not in {"ready_for_checkout", "in_checkout"}:
        raise business_error("Identification disponible uniquement avant le paiement en caisse")
    if customer_id is not None:
        require_customer(db, ticket.institute_id, customer_id)
    if ticket.customer_id == customer_id:
        return ticket
    from app.modules.gift_cards.tenders import require_no_active_tender
    require_no_active_tender(db, ticket)
    covered = db.scalar(select(PackageRedemption.id).join(
        TicketLine, TicketLine.id == PackageRedemption.ticket_line_id,
    ).where(TicketLine.ticket_id == ticket.id, PackageRedemption.reversed_at.is_(None)))
    if covered:
        raise business_error("Annuler l'utilisation du forfait avant de changer de cliente")
    from app.modules.memberships.models import MembershipBenefit
    if db.scalar(select(MembershipBenefit.id).join(TicketLine,
        TicketLine.id == MembershipBenefit.ticket_line_id).where(
        TicketLine.ticket_id == ticket.id, MembershipBenefit.reversed_at.is_(None))):
        raise business_error("Annuler l'avantage membre avant de changer de cliente")
    from app.modules.loyalty.redemption import require_no_reward
    require_no_reward(db, ticket=ticket)
    ticket.customer_id = customer_id
    record_event(db, ticket, "queue.customer_changed", ticket.status)
    db.commit()
    db.refresh(ticket)
    return ticket


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _generate_ticket_number(db: Session, institute_id: str) -> str:
    numbers = db.scalars(select(QueueTicket.ticket_number).where(
        QueueTicket.institute_id == institute_id,
    )).all()
    # Include historical tickets; seeded legacy numbers remain valid.
    last = max((int(number[2:]) for number in numbers
                if number.startswith("T-") and number[2:].isdigit()), default=0)
    return f"T-{last + 1:03d}"


def _ticket_duration(db: Session, ticket_id: str, fallback_minutes: int = 0) -> int:
    """Durée totale d'un ticket multi-prestations.

    Règle produit : la collaboratrice entre en cabine une seule fois.
    Le planning doit donc réserver une seule séance avec le cumul des durées.
    """
    total = sum(line.duration_minutes * line.quantity for line in _ticket_lines(db, ticket_id))
    return total or fallback_minutes


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
            select(TicketLine).where(TicketLine.invoice_removed_at.is_(None))
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


def _has_active_employee_blocker(db: Session, institute_id: str, employee_id: str, now: datetime | None = None) -> bool:
    now = now or utcnow()

    has_active_session = db.scalars(
        select(ServiceSession).where(
            ServiceSession.institute_id == institute_id,
            ServiceSession.employee_id == employee_id,
            ServiceSession.status.in_(ACTIVE_SESSION_STATUSES),
        )
    ).first() is not None

    has_active_appointment = db.scalars(
        select(Appointment).where(
            Appointment.institute_id == institute_id,
            Appointment.employee_id == employee_id,
            Appointment.status.in_(ACTIVE_APPOINTMENT_STATUSES),
            Appointment.start_time <= now,
            Appointment.end_time > now,
        )
    ).first() is not None

    return has_active_session or has_active_appointment


def estimate_start_time(db: Session, institute_id: str, service_duration_minutes: int,
                        service_ids: list[str] | None = None):
    from app.modules.scheduling.waiting_service import waiting_projections

    return waiting_projections(db, institute_id, new_duration=service_duration_minutes, new_service_ids=service_ids)[
        "__new_arrival__"
    ].estimated_start_time


def _creation_fingerprint(payload: TicketCreate) -> str:
    data = {"service_ids": sorted(_payload_service_ids(payload)), "customer_id": payload.customer_id,
            "subscription_id": payload.subscription_id, "created_by_id": payload.created_by_id}
    return sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def _validate_creation_replay(db: Session, ticket: QueueTicket, payload: TicketCreate) -> QueueTicket:
    if ticket.creation_fingerprint:
        if ticket.creation_fingerprint != _creation_fingerprint(payload):
            raise business_error("La cle de rejeu appartient a un autre ticket")
        return ticket
    if (sorted(line.service_id for line in _ticket_lines(db, ticket.id)) != sorted(_payload_service_ids(payload))
            or ticket.customer_id != payload.customer_id
            or ticket.subscription_id != payload.subscription_id
            or ticket.created_by_id != payload.created_by_id):
        raise business_error("La cle de rejeu appartient a un autre ticket")
    return ticket


def prepare_booking_checkout(db: Session, appointment: Appointment, actor_id: str | None = None) -> QueueTicket:
    """Create a performed-service checkout within the caller's institute transaction.

    The caller owns the institute lock and durable appointment link. No commit,
    waiting projection, employee assignment or capacity reservation is created.
    """
    service = get_service(db, appointment.service_id)
    if not service:
        raise not_found("Prestation du rendez-vous introuvable")
    ticket = QueueTicket(id=new_id("qt"), institute_id=appointment.institute_id,
                        customer_id=appointment.customer_id,
                        ticket_number=_generate_ticket_number(db, appointment.institute_id),
                        status="ready_for_checkout", arrival_time=appointment.actual_end_time or utcnow(),
                        total_amount=service.price_passage or 0)
    db.add(ticket)
    db.flush()
    from app.modules.tickets.currency import snapshot_currency
    snapshot_currency(db, ticket)
    duration = int((_ensure_aware(appointment.end_time) - _ensure_aware(appointment.start_time)).total_seconds() / 60)
    line_id = new_id("tl")
    db.add(TicketLine(id=line_id, ticket_id=ticket.id, service_id=service.id,
                     quantity=1, unit_price=service.price_passage, total=service.price_passage,
                     duration_minutes=max(1, duration), revenue_category="care",
                     performed_by_employee_id=appointment.employee_id))
    db.flush()
    from app.modules.appointments.models import AppointmentInvoiceLine
    db.add(AppointmentInvoiceLine(appointment_id=appointment.id, institute_id=appointment.institute_id,
        ticket_id=ticket.id, ticket_line_id=line_id, actor_id=actor_id,
        occurred_at=appointment.actual_end_time or utcnow()))
    record_event(db, ticket, "queue.booking_finished", None, appointment.employee_id)
    return ticket


def create_queue_ticket(db: Session, payload: TicketCreate) -> QueueTicket:
    lock_institute(db, payload.institute_id)
    if payload.idempotency_key:
        existing_ticket = get_ticket_by_idempotency_key(db, payload.institute_id, payload.idempotency_key)
        if existing_ticket:
            return _validate_creation_replay(db, existing_ticket, payload)

    if payload.created_by_id:
        creator = get_employee(db, payload.created_by_id)
        if not creator or creator.institute_id != payload.institute_id:
            raise business_error("Createur du ticket hors institut")

    from app.modules.customers.repository import validate_customer_reference
    validate_customer_reference(db, payload.institute_id, payload.customer_id)

    service_ids = _payload_service_ids(payload)
    if not service_ids:
        raise business_error("Ajoute au moins une prestation au ticket")

    services = []
    for service_id in service_ids:
        service = get_service(db, service_id)
        if not service:
            raise not_found(f"Prestation introuvable : {service_id}")
        if service.duration_min <= 0:
            raise business_error("La duree standard de la prestation est invalide")
        services.append(service)

    total_duration = sum(service.duration_min for service in services)
    total_amount = sum(float(service.price_passage or 0) for service in services)
    now = utcnow()
    ticket = QueueTicket(
        id=new_id("qt"),
        institute_id=payload.institute_id,
        ticket_number=_generate_ticket_number(db, payload.institute_id),
        idempotency_key=payload.idempotency_key,
        creation_fingerprint=_creation_fingerprint(payload),
        customer_id=payload.customer_id,
        subscription_id=payload.subscription_id,
        status="waiting",
        arrival_time=now,
        estimated_start_time=estimate_start_time(db, payload.institute_id, total_duration, service_ids),
        created_by_id=payload.created_by_id,
        total_amount=total_amount,
    )
    try:
        db.add(ticket)
        db.flush()
        from app.modules.tickets.currency import snapshot_currency
        snapshot_currency(db, ticket)
        for service in services:
            db.add(TicketLine(
                id=new_id("tl"), ticket_id=ticket.id, service_id=service.id,
                quantity=1, unit_price=service.price_passage, total=service.price_passage,
                duration_minutes=service.duration_min, revenue_category="care",
            ))
        record_event(db, ticket, "queue.arrived", None, payload.created_by_id)
        db.commit()
    except IntegrityError:
        db.rollback()
        if payload.idempotency_key:
            existing = get_ticket_by_idempotency_key(db, payload.institute_id, payload.idempotency_key)
            if existing:
                return _validate_creation_replay(db, existing, payload)
        raise
    db.refresh(ticket)
    return ticket


def ensure_employee_queue_capacity(db: Session, ticket: QueueTicket, employee_id: str) -> None:
    reserved = db.scalar(select(QueueTicket.id).where(
        QueueTicket.institute_id == ticket.institute_id,
        QueueTicket.assigned_employee_id == employee_id,
        QueueTicket.status == "assigned",
        QueueTicket.id != ticket.id,
    ))
    if reserved:
        raise business_error("La collaboratrice a deja un ticket affecte")
    now = utcnow()
    end = now + timedelta(minutes=_ticket_duration(db, ticket.id))
    from app.modules.workforce.absences import ensure_window
    ensure_window(db, ticket.institute_id, employee_id, now, end)
    appointment = db.scalar(select(Appointment.id).where(
        Appointment.institute_id == ticket.institute_id,
        Appointment.employee_id == employee_id,
        Appointment.status.in_(ACTIVE_APPOINTMENT_STATUSES),
        Appointment.start_time < end, Appointment.end_time > now,
    ))
    if appointment:
        raise business_error("La prestation chevauche un rendez-vous planifie")


def assign_ticket(db: Session, ticket_id: str, employee_id: str) -> QueueTicket:
    ticket = lock_ticket(db, ticket_id)
    if not ticket:
        raise not_found("Ticket introuvable")
    employee = get_employee(db, employee_id)
    if not employee:
        raise not_found("Collaboratrice introuvable")
    if employee.institute_id != ticket.institute_id:
        raise business_error("La collaboratrice ne fait pas partie de cet institut")

    if ticket.status == "assigned" and ticket.assigned_employee_id == employee.id:
        return ticket

    if ticket.status not in {"waiting", "assigned"}:
        raise business_error("Ce ticket est déjà en prestation, en caisse, payé ou annulé")

    if ticket.status == "assigned" and ticket.assigned_employee_id and ticket.assigned_employee_id != employee.id:
        raise business_error("Ce ticket est déjà affecté à une autre collaboratrice")

    if employee.status not in ASSIGNABLE_EMPLOYEE_STATUSES:
        raise business_error("La collaboratrice n'est pas disponible pour recevoir un ticket")

    if _has_active_employee_blocker(db, ticket.institute_id, employee.id):
        raise business_error("La collaboratrice est encore occupée par une prestation ou un rendez-vous en cours")

    ensure_employee_queue_capacity(db, ticket, employee.id)
    from app.modules.resources.repository import qualifies_for_services, ticket_services
    if not qualifies_for_services(db, ticket.institute_id, employee.id, ticket_services(db, ticket.institute_id, ticket.id)):
        raise business_error("La collaboratrice ne possede pas toutes les competences requises")
    from app.modules.resources.reservations import reserve_ticket
    reservation_start = utcnow()
    reservation_minutes = sum(line.duration_minutes * line.quantity for line in _ticket_lines(db, ticket.id))
    reserve_ticket(db, ticket, reservation_start, reservation_start + timedelta(minutes=reservation_minutes))
    transition_ticket(db, ticket, "assigned", "queue.assigned", employee.id)
    ticket.assigned_employee_id = employee.id
    ticket.assigned_at = utcnow()
    return save_ticket(db, ticket)


def unassign_ticket(db: Session, ticket_id: str) -> QueueTicket:
    ticket = lock_ticket(db, ticket_id)
    if ticket.status == "waiting" and ticket.assigned_employee_id is None:
        return ticket
    if ticket.status != "assigned":
        raise business_error("Seul un ticket affecte peut retourner en attente")
    from app.modules.resources.reservations import release
    release(db, ticket.institute_id, ticket_id=ticket.id)
    transition_ticket(db, ticket, "waiting", "queue.unassigned", ticket.assigned_employee_id)
    ticket.assigned_employee_id = None
    ticket.assigned_at = None
    return save_ticket(db, ticket)


def cancel_ticket(db: Session, ticket_id: str, actor_id: str | None = None) -> QueueTicket:
    ticket = lock_ticket(db, ticket_id)
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

    from app.modules.commerce.models import PackageRedemption
    if db.scalar(select(PackageRedemption.id).join(TicketLine, PackageRedemption.ticket_line_id == TicketLine.id)
                 .where(TicketLine.ticket_id == ticket.id, PackageRedemption.reversed_at.is_(None))):
        raise business_error("Annuler d'abord la consommation du forfait avant ce ticket")
    from app.modules.memberships.models import MembershipBenefit
    if db.scalar(select(MembershipBenefit.id).join(TicketLine, MembershipBenefit.ticket_line_id == TicketLine.id)
                 .where(TicketLine.ticket_id == ticket.id, MembershipBenefit.reversed_at.is_(None))):
        raise business_error("Annuler d'abord l'avantage membre avant ce ticket")

    from app.modules.gift_cards.tenders import require_no_active_tender
    require_no_active_tender(db, ticket)
    from app.modules.loyalty.redemption import require_no_reward
    require_no_reward(db, ticket=ticket)
    from app.modules.resources.reservations import release
    release(db, ticket.institute_id, ticket_id=ticket.id)
    transition_ticket(db, ticket, "cancelled", "queue.cancelled", ticket.assigned_employee_id, actor_id=actor_id)
    ticket.assigned_employee_id = None
    ticket.assigned_at = None
    ticket.cancelled_at = utcnow()
    ticket.estimated_start_time = None
    return save_ticket(db, ticket)


def add_checkout_ticket_line(db: Session, ticket_id: str, service_id: str) -> QueueTicket:
    """Ajoute une prestation au moment de l'encaissement.

    Cas terrain : pendant la séance, la cliente demande une prestation en plus.
    La collaboratrice ne sort pas de cabine pour modifier le ticket. Elle corrige
    le ticket juste avant d'encaisser.
    """
    ticket = lock_ticket(db, ticket_id)
    from app.modules.tickets.currency import require_current_catalog_currency
    from app.modules.gift_cards.tenders import require_no_active_tender
    require_no_active_tender(db, ticket)
    require_current_catalog_currency(db, ticket)
    if not ticket:
        raise not_found("Ticket introuvable")

    if ticket.status not in {"ready_for_checkout", "in_checkout"}:
        raise business_error("Les prestations se modifient à l'encaissement, après la séance")

    service = get_service(db, service_id)
    if not service:
        raise not_found("Prestation introuvable")

    performer_id = ticket.assigned_employee_id or ticket.checkout_employee_id or ticket.paid_employee_id
    unit_price = service.price_passage
    line = TicketLine(
        id=new_id("tl"),
        ticket_id=ticket.id,
        service_id=service.id,
        quantity=1,
        unit_price=unit_price,
        total=unit_price,
        duration_minutes=service.duration_min,
        revenue_category="care",
        performed_by_employee_id=performer_id,
    )

    db.add(line)
    ticket.total_amount = _ticket_total(db, ticket.id) + float(unit_price or 0)
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


def remove_checkout_ticket_line(db: Session, ticket_id: str, line_id: str, actor_id: str | None = None) -> QueueTicket:
    """Retire une prestation non réalisée avant le paiement."""
    ticket = lock_ticket(db, ticket_id)
    if not ticket:
        raise not_found("Ticket introuvable")

    line = db.get(TicketLine, line_id)
    if not line or line.ticket_id != ticket.id:
        raise not_found("Ligne de prestation introuvable")
    db.refresh(line)
    if line.invoice_removed_at is not None:
        if not actor_id or line.invoice_removed_by_actor != actor_id:
            raise business_error("Retrait original signe par un autre operateur")
        return ticket
    if ticket.status not in {"ready_for_checkout", "in_checkout"}:
        raise business_error("Les prestations se modifient uniquement a l'encaissement")
    from app.modules.gift_cards.tenders import require_no_active_tender
    require_no_active_tender(db, ticket)

    from app.modules.commerce.models import PackageRedemption
    if db.scalar(select(PackageRedemption.id).where(PackageRedemption.ticket_line_id == line.id)):
        raise business_error("L'historique commercial de cette prestation interdit sa suppression")
    from app.modules.memberships.models import MembershipBenefit
    if db.scalar(select(MembershipBenefit.id).where(MembershipBenefit.ticket_line_id == line.id)):
        raise business_error("L'historique des avantages interdit la suppression de cette prestation")

    from app.modules.loyalty.redemption import require_no_reward
    require_no_reward(db, line_id=line.id, history=True)
    lines = _ticket_lines(db, ticket.id)
    if len(lines) <= 1:
        raise business_error("Impossible de supprimer la dernière prestation du ticket")

    if not actor_id or not actor_id.strip() or len(actor_id) > 160:
        raise business_error("Operateur signe requis pour retirer une prestation")
    line.invoice_removed_at = utcnow()
    line.invoice_removed_by_actor = actor_id
    line.invoice_removal_reason = "not_performed"
    db.add(line)
    db.flush()
    ticket.total_amount = _ticket_total(db, ticket.id)
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


def start_checkout(db: Session, ticket_id: str, employee_id: str) -> QueueTicket:
    """Démarre l'encaissement après ré-identification collaboratrice.

    Règle produit : la personne qui a créé le ticket n'est pas forcément celle
    qui encaisse. L'encaissement doit donc enregistrer une nouvelle identité.
    """
    ticket = get_ticket(db, ticket_id)
    if not ticket:
        raise not_found("Ticket introuvable")

    lock_institute(db, ticket.institute_id)
    db.refresh(ticket)

    employee = get_employee(db, employee_id)
    if not employee:
        raise not_found("Collaboratrice introuvable")
    if employee.institute_id != ticket.institute_id:
        raise business_error("La collaboratrice ne fait pas partie de cet institut")

    if ticket.status not in {"ready_for_checkout", "in_checkout"}:
        raise business_error("Le ticket doit être prêt pour la caisse avant encaissement")

    if ticket.status == "in_checkout" and ticket.checkout_employee_id and ticket.checkout_employee_id != employee.id:
        raise business_error("Ce ticket est déjà ouvert en caisse par une autre collaboratrice")

    if ticket.status == "in_checkout" and ticket.checkout_employee_id == employee.id:
        return ticket
    # Reopening the same cashier is a read-only replay, including during recovery.
    # Every actual checkout mutation still requires an unprotected ticket.
    from app.modules.payments.executions import require_no_payment_execution
    require_no_payment_execution(db, ticket)
    transition_ticket(db, ticket, "in_checkout", "queue.checkout_started", employee.id)
    ticket.checkout_employee_id = employee.id
    ticket.checkout_started_at = ticket.checkout_started_at or utcnow()
    ticket.total_amount = _ticket_total(db, ticket.id)
    return save_ticket(db, ticket)


def complete_payment(db: Session, ticket_id: str, employee_id: str, payment_method: str,
                     remainder_method: str | None = None, actor: str | None = None,
                     operator_institute: str | None = None) -> QueueTicket:
    ticket = lock_ticket(db, ticket_id)
    if not ticket:
        raise not_found("Ticket introuvable")

    employee = get_employee(db, employee_id)
    if not employee:
        raise not_found("Collaboratrice introuvable")
    if employee.institute_id != ticket.institute_id:
        raise business_error("La collaboratrice ne fait pas partie de cet institut")

    if payment_method not in PAYMENT_METHODS:
        raise business_error("Mode de paiement invalide")

    if (ticket.status == "paid" and ticket.paid_employee_id == employee.id
            and ticket.payment_method == payment_method):
        from app.modules.gift_cards.tenders import validate_paid_replay
        validate_paid_replay(db, ticket, remainder_method)
        return ticket

    if ticket.status not in {"ready_for_checkout", "in_checkout"}:
        raise business_error("Ce ticket ne peut pas être payé dans son état actuel")

    if ticket.checkout_employee_id and ticket.checkout_employee_id != employee.id:
        raise business_error("La collaboratrice identifiée en caisse doit valider le paiement")

    from app.modules.gift_cards.tenders import validate_payment
    validate_payment(db, ticket, payment_method, remainder_method, actor)

    # Filet de sécurité : si une ligne n'a pas encore d'exécutante, on l'attribue
    # à la collaboratrice qui encaisse. Dans le flux normal, elle est déjà remplie
    # au démarrage de la prestation.
    for line in _ticket_lines(db, ticket.id):
        if not line.performed_by_employee_id:
            line.performed_by_employee_id = employee.id
            db.add(line)

    transition_ticket(db, ticket, "paid", "queue.paid", employee.id)
    ticket.checkout_employee_id = ticket.checkout_employee_id or employee.id
    ticket.checkout_started_at = ticket.checkout_started_at or utcnow()
    ticket.assigned_employee_id = None
    ticket.assigned_at = None
    ticket.paid_employee_id = employee.id
    ticket.paid_at = utcnow()
    ticket.payment_method = payment_method
    ticket.total_amount = _ticket_total(db, ticket.id)

    current_employee = get_employee(db, employee.id)
    from app.modules.loyalty.earning import award_checkout
    award_checkout(db, ticket, actor, operator_institute)
    if current_employee:
        current_appointment = db.scalars(
            select(Appointment)
            .where(
                Appointment.institute_id == current_employee.institute_id,
                Appointment.employee_id == current_employee.id,
                Appointment.status.in_(["scheduled", "confirmed", "arrived", "in_progress"]),
                Appointment.start_time <= utcnow(),
                Appointment.end_time > utcnow(),
            )
            .order_by(Appointment.end_time.asc())
        ).first()
        active_session = db.scalars(
            select(ServiceSession)
            .where(
                ServiceSession.institute_id == current_employee.institute_id,
                ServiceSession.employee_id == current_employee.id,
                ServiceSession.status.in_(["planned", "in_progress", "extended", "delayed"]),
            )
            .order_by(ServiceSession.planned_end_time.desc())
        ).first()
        if not current_appointment and not active_session and current_employee.status == "busy":
            current_employee.status = "available"
            db.add(current_employee)

    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


def get_chiffres_by_employee(db: Session, institute_id: str) -> dict:
    with localcontext() as context:
        context.prec = 28
        return _chiffres_by_employee(db, institute_id)


def _chiffres_by_employee(db: Session, institute_id: str, currency_filter=None, grouped=False, report_now=None, source_tickets=None) -> dict:
    """Calcule le module Chiffres par collaboratrice.

    Règle métier validée avec le client : les chiffres ne sont pas
    imputés à la personne qui a créé le ticket, mais à la collaboratrice qui a
    réalisé la prestation. Si une ligne n'a pas d'exécutante, on utilise la
    collaboratrice qui a validé l'encaissement comme filet de sécurité.
    """
    from app.modules.tickets.schemas import EmployeeChiffresRead, ChiffresSummaryRead, CurrencyChiffresRead

    now = report_now or utcnow()
    period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    period_end = period_start + timedelta(days=1)

    employees = list_by_institute(db, institute_id)
    employee_names = {employee.id: employee.first_name for employee in employees}

    rows_by_employee: dict[str, dict] = {
        employee.id: {
            "employee_id": employee.id,
            "employee_name": employee.first_name,
            "soins": Decimal("0.00"),
            "ventes": Decimal("0.00"),
            "contrats": Decimal("0.00"),
            "pourboires": Decimal("0.00"),
            "tickets": set(),
            "prestations": 0,
        }
        for employee in employees
    }

    paid_tickets = source_tickets if source_tickets is not None else list(
        db.scalars(
            select(QueueTicket).where(
                QueueTicket.institute_id == institute_id,
                QueueTicket.status == "paid",
                QueueTicket.paid_at >= period_start,
                QueueTicket.paid_at < period_end,
            )
        ).all()
    )

    if grouped:
        paid_tickets = [ticket for ticket in paid_tickets if ticket.currency == currency_filter]

    for ticket in paid_tickets:
        lines = _ticket_lines(db, ticket.id)
        for line in lines:
            employee_id = line.performed_by_employee_id or ticket.paid_employee_id or ticket.checkout_employee_id
            if not employee_id:
                continue

            if employee_id not in rows_by_employee:
                rows_by_employee[employee_id] = {
                    "employee_id": employee_id,
                    "employee_name": employee_names.get(employee_id, "Collaboratrice"),
                    "soins": Decimal("0.00"),
                    "ventes": Decimal("0.00"),
                    "contrats": Decimal("0.00"),
                    "pourboires": Decimal("0.00"),
                    "tickets": set(),
                    "prestations": 0,
                }

            amount = Decimal(str(line.total or 0))
            category = (line.revenue_category or "care").lower()
            target = rows_by_employee[employee_id]

            if category in {"care", "soin", "soins", "prestation"}:
                target["soins"] += amount
                target["prestations"] += int(line.quantity or 1)
            elif category in {"sale", "vente", "ventes", "product", "produit"}:
                target["ventes"] += amount
            elif category in {"contract", "contrat", "contrats", "subscription", "abonnement"}:
                target["contrats"] += amount
            elif category in {"tip", "tips", "pourboire", "pourboires"}:
                target["pourboires"] += amount
            else:
                # Par défaut, une ligne inconnue reste dans Soins pour ne pas perdre le CA.
                target["soins"] += amount
                target["prestations"] += int(line.quantity or 1)

            target["tickets"].add(ticket.id)

    rows: list[EmployeeChiffresRead] = []
    total_soins = total_ventes = total_contrats = total_pourboires = Decimal("0.00")
    total_tickets: set[str] = set()
    total_prestations = 0

    for employee_id, item in rows_by_employee.items():
        total = item["soins"] + item["ventes"] + item["contrats"] + item["pourboires"]
        ticket_count = len(item["tickets"])
        prestations_count = int(item["prestations"])
        moyenne = total / ticket_count if ticket_count else 0.0

        total_soins += item["soins"]
        total_ventes += item["ventes"]
        total_contrats += item["contrats"]
        total_pourboires += item["pourboires"]
        total_tickets.update(item["tickets"])
        total_prestations += prestations_count

        rows.append(
            EmployeeChiffresRead(
                employee_id=employee_id,
                employee_name=item["employee_name"],
                soins=round(item["soins"], 2),
                ventes=round(item["ventes"], 2),
                contrats=round(item["contrats"], 2),
                pourboires=round(item["pourboires"], 2),
                moyenne=round(moyenne, 2),
                total=round(total, 2),
                tickets=ticket_count,
                prestations=prestations_count,
            )
        )

    rows = sorted(rows, key=lambda row: row.employee_name.lower())
    grand_total = total_soins + total_ventes + total_contrats + total_pourboires
    grand_ticket_count = len(total_tickets)

    summary = ChiffresSummaryRead(
        institute_id=institute_id,
        generated_at=now,
        period_start=period_start,
        period_end=period_end,
        rows=rows,
        totals=EmployeeChiffresRead(
            employee_id="total",
            employee_name="TOTAL",
            soins=round(total_soins, 2),
            ventes=round(total_ventes, 2),
            contrats=round(total_contrats, 2),
            pourboires=round(total_pourboires, 2),
            moyenne=round(grand_total / grand_ticket_count, 2) if grand_ticket_count else 0.0,
            total=round(grand_total, 2),
            tickets=grand_ticket_count,
            prestations=total_prestations,
        ),
    )

    if grouped:
        summary.currency = currency_filter
        return summary
    currencies = sorted({ticket.currency for ticket in paid_tickets if ticket.currency in {"CHF", "EUR"}})
    summary.unknown_currency_tickets = sum(ticket.currency not in {"CHF", "EUR"} for ticket in paid_tickets)
    for currency in currencies:
        group = _chiffres_by_employee(db, institute_id, currency, True, now, paid_tickets)
        summary.currency_groups.append(CurrencyChiffresRead(currency=currency, rows=group.rows, totals=group.totals))
    if len(currencies) == 1 and not summary.unknown_currency_tickets:
        summary.currency = currencies[0]
    elif paid_tickets:
        for row in [*summary.rows, summary.totals]:
            for field in ("soins", "ventes", "contrats", "pourboires", "moyenne", "total"):
                setattr(row, field, None)
    return summary
