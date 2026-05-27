from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.employees.models import Employee


def list_by_institute(db: Session, institute_id: str) -> list[Employee]:
    return list(
        db.scalars(
            select(Employee)
            .where(Employee.institute_id == institute_id)
            .order_by(Employee.first_name)
        ).all()
    )


def get_employee(db: Session, employee_id: str) -> Employee | None:
    return db.get(Employee, employee_id)


def save_employee(db: Session, employee: Employee) -> Employee:
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return employee
