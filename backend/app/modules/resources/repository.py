from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.employees.models import Employee
from app.modules.resources.models import EmployeeSkill, ResourceRequirement, ServiceRequirement
from app.modules.resources.domain import has_required_skills
from app.modules.tickets.models import QueueTicket, TicketLine


def skill_facts(db: Session, institute_id: str) -> dict[str, set[str]]:
    # Legacy JSON stays readable while existing callers progressively migrate.
    # Configuration writes synchronize both representations transactionally.
    facts = {employee.id: {code for code in employee.skills if isinstance(code, str)}
             for employee in db.scalars(select(Employee).where(
                 Employee.institute_id == institute_id).execution_options(populate_existing=True)).all()}
    for employee_id, code in db.execute(select(EmployeeSkill.employee_id, EmployeeSkill.skill_code).where(
            EmployeeSkill.institute_id == institute_id)):
        if employee_id in facts:
            facts[employee_id].add(code)
    return facts


def requirement_facts(db: Session, institute_id: str) -> dict[str, set[str]]:
    requirements: dict[str, set[str]] = {}
    for service_id, code in db.execute(select(ServiceRequirement.service_id, ServiceRequirement.skill_code).where(
            ServiceRequirement.institute_id == institute_id)):
        requirements.setdefault(service_id, set()).add(code)
    return requirements


def resource_requirement_facts(db: Session, institute_id: str) -> dict[str, list[tuple[str, str, int]]]:
    requirements: dict[str, list[tuple[str, str, int]]] = {}
    for service_id, kind, capability, quantity in db.execute(select(
            ResourceRequirement.service_id, ResourceRequirement.kind, ResourceRequirement.capability,
            ResourceRequirement.quantity).where(ResourceRequirement.institute_id == institute_id)):
        requirements.setdefault(service_id, []).append((kind, capability, quantity))
    return requirements


def ensure_resource_capacity_known(db: Session, institute_id: str, service_ids: list[str]):
    # Phase 5A stores explicit needs; Phase 5B will resolve and reserve them.
    # Until a reservation can be proven, never admit a resource-dependent write.
    from app.shared.exceptions import business_error
    requirements = resource_requirement_facts(db, institute_id)
    if any(requirements.get(service_id) for service_id in service_ids):
        raise business_error("La capacite des ressources de cette prestation ne peut pas etre confirmee")


def ticket_services(db: Session, institute_id: str, ticket_id: str) -> list[str]:
    return list(db.scalars(select(TicketLine.service_id).where(TicketLine.invoice_removed_at.is_(None)).join(QueueTicket, QueueTicket.id == TicketLine.ticket_id).where(
        QueueTicket.institute_id == institute_id, QueueTicket.id == ticket_id,
    )).all())


def qualifies_for_services(db: Session, institute_id: str, employee_id: str, service_ids: list[str]) -> bool:
    skills = skill_facts(db, institute_id)
    requirements = requirement_facts(db, institute_id)
    needed = set().union(*(requirements.get(service_id, set()) for service_id in service_ids))
    return employee_id in skills and has_required_skills(skills[employee_id], needed)
