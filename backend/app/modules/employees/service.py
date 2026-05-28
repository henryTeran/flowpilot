from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.employees.models import Employee
from app.modules.employees.repository import get_employee, save_employee
from app.modules.employees.schemas import EmployeeCreate
from app.modules.planning.models import ServiceSession
from app.shared.exceptions import business_error, not_found
from app.shared.ids import new_id

ALLOWED_EMPLOYEE_STATUSES = {"available", "busy", "pause", "absent", "offline"}
ACTIVE_SESSION_STATUSES = ["planned", "in_progress", "extended", "delayed"]


def create_employee(db: Session, payload: EmployeeCreate) -> Employee:
    employee = Employee(id=new_id("emp"), **payload.model_dump())
    return save_employee(db, employee)


def change_employee_status(db: Session, employee_id: str, status: str) -> Employee:
    if status not in ALLOWED_EMPLOYEE_STATUSES:
        raise ValueError(f"Statut collaboratrice invalide: {status}")

    employee = get_employee(db, employee_id)
    if not employee:
        raise not_found("Collaboratrice introuvable")

    if status == "available":
        active_session = db.scalars(
            select(ServiceSession).where(
                ServiceSession.employee_id == employee.id,
                ServiceSession.institute_id == employee.institute_id,
                ServiceSession.status.in_(ACTIVE_SESSION_STATUSES),
            )
        ).first()
        if active_session:
            raise business_error(
                "Impossible de rendre cette collaboratrice disponible : une prestation est encore en cours. Clique d’abord sur Fin."
            )

    employee.status = status
    return save_employee(db, employee)
