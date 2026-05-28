from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.appointments.models import Appointment
from app.modules.appointments.repository import (
    ACTIVE_APPOINTMENT_STATUSES,
    FINAL_APPOINTMENT_STATUSES,
    get_appointment,
    list_appointments_for_day,
    save_appointment,
)
from app.modules.appointments.schemas import AppointmentCreate
from app.modules.employees.models import Employee
from app.modules.employees.repository import get_employee
from app.modules.planning.models import ServiceSession
from app.modules.services.repository import get_service
from app.shared.exceptions import business_error, not_found
from app.shared.ids import new_id
from app.shared.time import utcnow

ACTIVE_SESSION_STATUSES = ["planned", "in_progress", "extended", "delayed"]


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _has_overlap(start_a: datetime, end_a: datetime, start_b: datetime, end_b: datetime) -> bool:
    start_a = _ensure_aware(start_a)
    end_a = _ensure_aware(end_a)
    start_b = _ensure_aware(start_b)
    end_b = _ensure_aware(end_b)
    return start_a < end_b and end_a > start_b


def _get_active_employee_session(db: Session, institute_id: str, employee_id: str) -> ServiceSession | None:
    return db.scalars(
        select(ServiceSession)
        .where(
            ServiceSession.institute_id == institute_id,
            ServiceSession.employee_id == employee_id,
            ServiceSession.status.in_(ACTIVE_SESSION_STATUSES),
        )
        .order_by(ServiceSession.planned_end_time.desc())
    ).first()


def _get_current_employee_appointment(
    db: Session,
    institute_id: str,
    employee_id: str,
    exclude_appointment_id: str | None = None,
) -> Appointment | None:
    now = utcnow()
    conditions = [
        Appointment.institute_id == institute_id,
        Appointment.employee_id == employee_id,
        Appointment.status.in_(ACTIVE_APPOINTMENT_STATUSES),
        Appointment.start_time <= now,
        Appointment.end_time > now,
    ]

    if exclude_appointment_id:
        conditions.append(Appointment.id != exclude_appointment_id)

    return db.scalars(
        select(Appointment)
        .where(*conditions)
        .order_by(Appointment.end_time.asc())
    ).first()


def _sync_employee_status(db: Session, employee: Employee, exclude_appointment_id: str | None = None) -> None:
    """Synchronise le statut opérationnel après une action RDV.

    Règle métier : une collaboratrice est disponible seulement si elle n'a ni
    prestation active, ni RDV actif sur le créneau courant.
    """
    active_session = _get_active_employee_session(db, employee.institute_id, employee.id)
    current_appointment = _get_current_employee_appointment(
        db=db,
        institute_id=employee.institute_id,
        employee_id=employee.id,
        exclude_appointment_id=exclude_appointment_id,
    )

    if employee.status in {"absent", "offline"}:
        return

    employee.status = "busy" if active_session or current_appointment else "available"
    db.add(employee)


def _assert_not_final(appointment: Appointment) -> None:
    if appointment.status in FINAL_APPOINTMENT_STATUSES:
        raise business_error("Ce rendez-vous est déjà clôturé, annulé ou marqué absent")


def list_today_appointments(db: Session, institute_id: str) -> list[Appointment]:
    return list_appointments_for_day(db, institute_id, utcnow())


def create_appointment(db: Session, payload: AppointmentCreate) -> Appointment:
    service = get_service(db, payload.service_id)
    if not service:
        raise not_found("Prestation introuvable")

    employee = get_employee(db, payload.employee_id)
    if not employee:
        raise not_found("Collaboratrice introuvable")

    if employee.institute_id != payload.institute_id:
        raise business_error("La collaboratrice ne fait pas partie de cet institut")

    start_time = _ensure_aware(payload.start_time)
    if start_time < utcnow() - timedelta(minutes=2):
        raise business_error("Le rendez-vous ne peut pas être créé dans le passé")

    duration = service.duration_max or service.duration_min
    end_time = start_time + timedelta(minutes=duration)

    active_sessions = list(
        db.scalars(
            select(ServiceSession).where(
                ServiceSession.institute_id == payload.institute_id,
                ServiceSession.employee_id == payload.employee_id,
                ServiceSession.status.in_(ACTIVE_SESSION_STATUSES),
            )
        ).all()
    )
    for session in active_sessions:
        if _has_overlap(start_time, end_time, session.start_time, session.planned_end_time):
            raise business_error(
                f"Conflit planning : {employee.first_name} a déjà une prestation sur ce créneau."
            )

    active_appointments = list(
        db.scalars(
            select(Appointment).where(
                Appointment.institute_id == payload.institute_id,
                Appointment.employee_id == payload.employee_id,
                Appointment.status.in_(ACTIVE_APPOINTMENT_STATUSES),
            )
        ).all()
    )
    for appointment in active_appointments:
        if _has_overlap(start_time, end_time, appointment.start_time, appointment.end_time):
            raise business_error(
                f"Conflit RDV : {employee.first_name} a déjà un rendez-vous sur ce créneau."
            )

    appointment = Appointment(
        id=new_id("appt"),
        institute_id=payload.institute_id,
        service_id=payload.service_id,
        employee_id=payload.employee_id,
        customer_name=payload.customer_name.strip(),
        phone=payload.phone.strip() if payload.phone else None,
        start_time=start_time,
        end_time=end_time,
        status="scheduled",
        notes=payload.notes.strip() if payload.notes else None,
    )
    return save_appointment(db, appointment)


def mark_appointment_arrived(db: Session, appointment_id: str) -> Appointment:
    appointment = get_appointment(db, appointment_id)
    if not appointment:
        raise not_found("Rendez-vous introuvable")

    if appointment.status not in {"scheduled", "confirmed"}:
        raise business_error("Seul un rendez-vous planifié peut passer en arrivée")

    appointment.status = "arrived"
    db.add(appointment)
    employee = get_employee(db, appointment.employee_id)
    if employee:
        _sync_employee_status(db, employee)
    db.commit()
    db.refresh(appointment)
    return appointment


def start_appointment(db: Session, appointment_id: str) -> Appointment:
    appointment = get_appointment(db, appointment_id)
    if not appointment:
        raise not_found("Rendez-vous introuvable")

    if appointment.status not in {"scheduled", "confirmed", "arrived"}:
        raise business_error("Ce rendez-vous ne peut pas être démarré")

    employee = get_employee(db, appointment.employee_id)
    if not employee:
        raise not_found("Collaboratrice introuvable")

    active_session = _get_active_employee_session(db, appointment.institute_id, appointment.employee_id)
    if active_session:
        raise business_error(
            f"{employee.first_name} a déjà une prestation active. Termine-la avant de démarrer le RDV."
        )

    now = utcnow()
    if now < _ensure_aware(appointment.start_time) - timedelta(minutes=15):
        raise business_error("Ce rendez-vous est encore trop tôt pour être démarré")

    appointment.status = "in_progress"
    employee.status = "busy"
    db.add(appointment)
    db.add(employee)
    db.commit()
    db.refresh(appointment)
    return appointment


def complete_appointment(db: Session, appointment_id: str) -> Appointment:
    appointment = get_appointment(db, appointment_id)
    if not appointment:
        raise not_found("Rendez-vous introuvable")

    if appointment.status not in {"arrived", "in_progress"}:
        raise business_error("Seul un rendez-vous arrivé ou en cours peut être terminé")

    appointment.status = "completed"
    employee = get_employee(db, appointment.employee_id)
    if employee:
        _sync_employee_status(db, employee, exclude_appointment_id=appointment.id)

    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    return appointment


def mark_appointment_no_show(db: Session, appointment_id: str) -> Appointment:
    appointment = get_appointment(db, appointment_id)
    if not appointment:
        raise not_found("Rendez-vous introuvable")

    if appointment.status not in {"scheduled", "confirmed", "arrived"}:
        raise business_error("Ce rendez-vous ne peut pas être marqué absent")

    appointment.status = "no_show"
    employee = get_employee(db, appointment.employee_id)
    if employee:
        _sync_employee_status(db, employee, exclude_appointment_id=appointment.id)

    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    return appointment


def cancel_appointment(db: Session, appointment_id: str) -> Appointment:
    appointment = get_appointment(db, appointment_id)
    if not appointment:
        raise not_found("Rendez-vous introuvable")

    _assert_not_final(appointment)

    if appointment.status == "in_progress":
        raise business_error("Un rendez-vous en cours doit être terminé, pas annulé")

    appointment.status = "cancelled"
    employee = get_employee(db, appointment.employee_id)
    if employee:
        _sync_employee_status(db, employee, exclude_appointment_id=appointment.id)

    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    return appointment
