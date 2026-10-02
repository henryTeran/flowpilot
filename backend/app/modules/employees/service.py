from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.appointments.models import Appointment
from app.modules.appointments.repository import ACTIVE_APPOINTMENT_STATUSES
from app.modules.employees.models import Employee
from app.modules.employees.repository import get_employee, save_employee
from app.modules.employees.schemas import EmployeeCreate
from app.modules.planning.models import ServiceSession
from app.modules.tickets.models import QueueTicket
from app.modules.tickets.repository import lock_institute
from app.shared.exceptions import business_error, not_found
from app.shared.ids import new_id
from app.shared.time import utcnow

ALLOWED_EMPLOYEE_STATUSES = {"available", "busy", "pause", "absent", "offline"}
ACTIVE_SESSION_STATUSES = ["planned", "in_progress", "extended", "delayed"]


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _get_current_employee_appointment(db: Session, employee: Employee) -> Appointment | None:
    now = utcnow()
    return db.scalars(
        select(Appointment).where(
            Appointment.institute_id == employee.institute_id,
            Appointment.employee_id == employee.id,
            Appointment.status.in_(ACTIVE_APPOINTMENT_STATUSES),
            Appointment.start_time <= now,
            Appointment.end_time > now,
        )
    ).first()


def create_employee(db: Session, payload: EmployeeCreate) -> Employee:
    employee = Employee(id=new_id("emp"), **payload.model_dump())
    return save_employee(db, employee)


def change_employee_status(db: Session, employee_id: str, status: str) -> Employee:
    if status not in ALLOWED_EMPLOYEE_STATUSES:
        raise ValueError(f"Statut collaboratrice invalide: {status}")

    employee = get_employee(db, employee_id)
    if not employee:
        raise not_found("Collaboratrice introuvable")

    lock_institute(db, employee.institute_id)
    db.refresh(employee)
    if status != "available" and db.scalar(select(QueueTicket.id).where(
        QueueTicket.institute_id == employee.institute_id,
        QueueTicket.assigned_employee_id == employee.id,
        QueueTicket.status == "assigned",
    )):
        raise business_error("Libere le ticket affecte avant de modifier le statut")

    active_session = db.scalars(
        select(ServiceSession).where(
            ServiceSession.employee_id == employee.id,
            ServiceSession.institute_id == employee.institute_id,
            ServiceSession.status.in_(ACTIVE_SESSION_STATUSES),
        )
    ).first()
    current_appointment = _get_current_employee_appointment(db, employee)

    if status in {"available", "pause", "absent", "offline"}:
        if active_session:
            raise business_error(
                "Impossible de modifier le statut de cette collaboratrice : une prestation est encore en cours. Termine-la d’abord."
            )
        if current_appointment:
            raise business_error(
                "Impossible de modifier le statut de cette collaboratrice : un rendez-vous sous appel est en cours."
            )

    if status == "available":
        employee.status = status
        return save_employee(db, employee)

    if status in {"pause", "absent", "offline"} and (active_session or current_appointment):
        raise business_error(
            "Cette collaboratrice est encore occupée et ne peut pas changer vers un statut hors service."
        )

    employee.status = status
    return save_employee(db, employee)
