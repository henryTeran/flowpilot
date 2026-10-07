from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.appointments.models import Appointment
from app.modules.employees.models import Employee
from app.modules.planning.models import ServiceSession
from app.modules.resources.models import EmployeeSkill, Resource, ResourceConfigurationEvent, ResourceRequirement, ResourceReservation, ServiceRequirement
from app.modules.resources.repository import requirement_facts, skill_facts
from app.modules.resources.domain import has_required_skills
from app.modules.resources.schemas import RequirementUpdate, ResourceCreate, ResourceUpdate, SkillUpdate
from app.modules.scheduling.repository import ACTIVE_APPOINTMENT_STATUSES, ACTIVE_SESSION_STATUSES
from app.modules.services.models import Service
from app.modules.tickets.models import QueueTicket, TicketLine
from app.modules.tickets.repository import lock_institute
from app.shared.exceptions import business_error, not_found
from app.shared.ids import new_id
from app.shared.time import utcnow


def _event(db, institute_id, event_type, target_id, actor_id):
    db.add(ResourceConfigurationEvent(id=new_id("rce"), institute_id=institute_id,
        event_type=event_type, target_id=target_id, actor_id=actor_id, occurred_at=utcnow()))


def sync_employee_skills(db: Session, employee: Employee) -> None:
    db.flush()
    db.execute(delete(EmployeeSkill).where(EmployeeSkill.employee_id == employee.id,
                                           EmployeeSkill.institute_id == employee.institute_id))
    for code in sorted({code for code in employee.skills if isinstance(code, str)}):
        db.add(EmployeeSkill(institute_id=employee.institute_id, employee_id=employee.id, skill_code=code))


def _employee(db, institute_id, employee_id):
    employee = db.scalar(select(Employee).where(Employee.id == employee_id, Employee.institute_id == institute_id)
                         .execution_options(populate_existing=True))
    if employee is None:
        raise not_found("Collaboratrice introuvable")
    return employee


def update_employee_skills(db: Session, institute_id: str, employee_id: str, payload: SkillUpdate, actor_id=None, *, commit=True):
    lock_institute(db, institute_id)
    employee = _employee(db, institute_id, employee_id)
    codes = sorted(payload.skills)
    if sorted(set(employee.skills)) == codes and skill_facts(db, institute_id).get(employee_id, set()) == set(codes):
        return employee.skills
    committed_services = set(db.scalars(select(TicketLine.service_id).where(TicketLine.invoice_removed_at.is_(None)).join(
        QueueTicket, QueueTicket.id == TicketLine.ticket_id).where(
        QueueTicket.institute_id == institute_id, QueueTicket.assigned_employee_id == employee_id,
        QueueTicket.status.in_(["assigned", "in_progress"]))).all())
    committed_services.update(db.scalars(select(Appointment.service_id).where(
        Appointment.institute_id == institute_id, Appointment.employee_id == employee_id,
        Appointment.status.in_(ACTIVE_APPOINTMENT_STATUSES))).all())
    committed_services.update(db.scalars(select(ServiceSession.service_id).where(
        ServiceSession.institute_id == institute_id, ServiceSession.employee_id == employee_id,
        ServiceSession.status.in_(ACTIVE_SESSION_STATUSES))).all())
    required = requirement_facts(db, institute_id)
    if any(not has_required_skills(codes, required.get(service_id, set())) for service_id in committed_services):
        raise business_error("Une competence est requise par une prestation ou une reservation existante")
    employee.skills = codes
    sync_employee_skills(db, employee)
    _event(db, institute_id, "employee.skills_updated", employee_id, actor_id)
    if commit:
        db.commit()
    return codes


def list_resources(db: Session, institute_id: str):
    return list(db.scalars(select(Resource).where(Resource.institute_id == institute_id).order_by(Resource.name, Resource.id)).all())


def create_resource(db: Session, institute_id: str, payload: ResourceCreate, actor_id=None):
    lock_institute(db, institute_id)
    values = payload.model_dump()
    values["capabilities"] = sorted(set(values["capabilities"]))
    existing = db.scalar(select(Resource).where(Resource.institute_id == institute_id, Resource.name == payload.name))
    if existing:
        if all(getattr(existing, key) == value for key, value in values.items()):
            return existing
        raise business_error("Une ressource porte deja ce nom")
    resource = Resource(id=new_id("res"), institute_id=institute_id, **values)
    db.add(resource)
    _event(db, institute_id, "resource.created", resource.id, actor_id)
    db.commit()
    db.refresh(resource)
    return resource


def update_resource(db: Session, institute_id: str, resource_id: str, payload: ResourceUpdate, actor_id=None):
    lock_institute(db, institute_id)
    resource = db.scalar(select(Resource).where(Resource.id == resource_id, Resource.institute_id == institute_id)
                         .execution_options(populate_existing=True))
    if resource is None:
        raise not_found("Ressource introuvable")
    values = payload.model_dump(exclude_unset=True, exclude_none=True)
    if "capabilities" in values:
        values["capabilities"] = sorted(set(values["capabilities"]))
    if all(getattr(resource, key) == value for key, value in values.items()):
        return resource
    if any(key in values and getattr(resource, key) != values[key] for key in ("capabilities", "status")):
        committed = db.scalar(select(ResourceReservation.id).where(
            ResourceReservation.institute_id == institute_id, ResourceReservation.resource_id == resource_id,
            ResourceReservation.status != "released"))
        if committed:
            raise business_error("Libere les reservations avant de modifier la capacite de cette ressource")
    for key, value in values.items():
        setattr(resource, key, value)
    _event(db, institute_id, "resource.updated", resource_id, actor_id)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise business_error("Une ressource porte deja ce nom")
    db.refresh(resource)
    return resource


def read_requirements(db: Session, institute_id: str, service_id: str):
    if db.get(Service, service_id) is None:
        raise not_found("Prestation introuvable")
    skills = sorted(requirement_facts(db, institute_id).get(service_id, set()))
    needs = db.scalars(select(ResourceRequirement).where(ResourceRequirement.institute_id == institute_id,
                                                       ResourceRequirement.service_id == service_id)).all()
    return {"skills": skills, "resources": [{"kind": need.kind, "capability": need.capability or None,
             "quantity": need.quantity} for need in sorted(needs, key=lambda need: (need.kind, need.capability))]}


def update_requirements(db: Session, institute_id: str, service_id: str, payload: RequirementUpdate, actor_id=None):
    lock_institute(db, institute_id)
    current = read_requirements(db, institute_id, service_id)
    proposed = {"skills": sorted(payload.skills), "resources": sorted(
        [need.model_dump() for need in payload.resources], key=lambda need: (need["kind"], need["capability"] or ""))}
    if current == proposed:
        return current
    reserved_ticket = db.scalar(select(QueueTicket.id).join(TicketLine, TicketLine.ticket_id == QueueTicket.id).where(
        QueueTicket.institute_id == institute_id, QueueTicket.status.in_(["assigned", "in_progress"]),
        TicketLine.service_id == service_id, TicketLine.invoice_removed_at.is_(None)))
    booked = db.scalar(select(Appointment.id).where(Appointment.institute_id == institute_id,
        Appointment.service_id == service_id, Appointment.status.in_(ACTIVE_APPOINTMENT_STATUSES)))
    active = db.scalar(select(ServiceSession.id).where(ServiceSession.institute_id == institute_id,
        ServiceSession.service_id == service_id, ServiceSession.status.in_(ACTIVE_SESSION_STATUSES)))
    if reserved_ticket or booked or active:
        raise business_error("Libere les prestations et reservations avant de modifier leurs exigences")
    db.execute(delete(ServiceRequirement).where(ServiceRequirement.institute_id == institute_id,
                                               ServiceRequirement.service_id == service_id))
    db.execute(delete(ResourceRequirement).where(ResourceRequirement.institute_id == institute_id,
                                                ResourceRequirement.service_id == service_id))
    for code in proposed["skills"]:
        db.add(ServiceRequirement(institute_id=institute_id, service_id=service_id, skill_code=code))
    for need in proposed["resources"]:
        db.add(ResourceRequirement(id=new_id("rrq"), institute_id=institute_id, service_id=service_id,
                                  kind=need["kind"], capability=need["capability"] or "", quantity=need["quantity"]))
    _event(db, institute_id, "service.requirements_updated", service_id, actor_id)
    db.commit()
    return proposed
