from sqlalchemy.orm import Session

from app.modules.employees.models import Employee
from app.modules.employees.repository import get_employee, save_employee
from app.modules.employees.schemas import EmployeeCreate
from app.shared.exceptions import not_found
from app.shared.ids import new_id

ALLOWED_EMPLOYEE_STATUSES = {"available", "busy", "pause", "absent", "offline"}


def create_employee(db: Session, payload: EmployeeCreate) -> Employee:
    employee = Employee(id=new_id("emp"), **payload.model_dump())
    return save_employee(db, employee)


def change_employee_status(db: Session, employee_id: str, status: str) -> Employee:
    if status not in ALLOWED_EMPLOYEE_STATUSES:
        raise ValueError(f"Statut collaboratrice invalide: {status}")
    employee = get_employee(db, employee_id)
    if not employee:
        raise not_found("Collaboratrice introuvable")
    employee.status = status
    return save_employee(db, employee)
