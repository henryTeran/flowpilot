from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.employees.models import Employee
from app.modules.resources.domain import has_required_skills
from app.modules.resources.repository import requirement_facts, skill_facts
from app.modules.services.models import Service
from app.modules.tickets.repository import lock_institute
from app.shared.time import utcnow


def read_skill_matrix(db: Session, institute_id: str, employee_offset: int = 0, employee_limit: int = 10,
                      service_offset: int = 0, service_limit: int = 10):
    # Serialize this bounded read with existing skill/requirement configuration
    # writes: never union legacy pre-write skills with structured post-write facts.
    # The dependency's session close releases the read transaction and row lock.
    lock_institute(db, institute_id)
    employee_filter = Employee.institute_id == institute_id
    service_filter = Service.status == "active"
    employee_total = db.scalar(select(func.count()).select_from(Employee).where(employee_filter))
    service_total = db.scalar(select(func.count()).select_from(Service).where(service_filter))
    employees = list(db.scalars(select(Employee).where(employee_filter).order_by(Employee.id)
                               .offset(employee_offset).limit(employee_limit)).all())
    services = list(db.scalars(select(Service).where(service_filter).order_by(Service.id)
                              .offset(service_offset).limit(service_limit)).all())
    skills = skill_facts(db, institute_id, [employee.id for employee in employees])
    required = requirement_facts(db, institute_id, [service.id for service in services])
    return {
        "institute_id": institute_id, "generated_at": utcnow(),
        "employee_page": {"offset": employee_offset, "limit": employee_limit, "total": employee_total},
        "service_page": {"offset": service_offset, "limit": service_limit, "total": service_total},
        "employees": [{"id": employee.id, "first_name": employee.first_name, "status": employee.status,
                       "skills": sorted(skills[employee.id])} for employee in employees],
        "services": [{"id": service.id, "name": service.name,
                      "required_skills": sorted(required.get(service.id, set())),
                      "requirement_state": "recorded" if required.get(service.id) else "none_recorded"}
                     for service in services],
        "cells": [{"employee_id": employee.id, "service_id": service.id,
                   "meets_recorded_requirements": has_required_skills(skills[employee.id], required.get(service.id, set())),
                   "missing_skills": sorted(required.get(service.id, set()) - skills[employee.id])}
                  for employee in employees for service in services],
    }
