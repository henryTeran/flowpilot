from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.employees.models import Employee


def list_by_institute(
    db: Session,
    institute_id: str,
    limit: int | None = None,
    offset: int | None = None,
) -> list[Employee]:
    stmt = select(Employee).where(Employee.institute_id == institute_id).order_by(Employee.first_name)
    if limit is not None:
        stmt = stmt.limit(limit)
    if offset is not None:
        stmt = stmt.offset(offset)
    return list(db.scalars(stmt).all())


def get_employee(db: Session, employee_id: str) -> Employee | None:
    return db.get(Employee, employee_id)


def save_employee(db: Session, employee: Employee) -> Employee:
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return employee
