"""Load tenant-scoped facts once and feed the pure waiting-time engine."""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.appointments.models import Appointment
from app.modules.employees.models import Employee
from app.modules.planning.models import ServiceSession
from app.modules.scheduling.repository import ACTIVE_APPOINTMENT_STATUSES, ACTIVE_SESSION_STATUSES
from app.modules.scheduling.waiting_domain import EmployeeTimeline, QueueWork, project_queue
from app.modules.tickets.models import QueueTicket, TicketLine
from app.shared.time import utcnow


def aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def waiting_projections(db: Session, institute_id: str, now: datetime | None = None,
                        new_duration: int | None = None, new_service_ids: list[str] | None = None):
    now = aware(now or utcnow())
    from app.modules.resources.repository import requirement_facts, resource_requirement_facts, skill_facts
    qualifications = skill_facts(db, institute_id)
    requirements = requirement_facts(db, institute_id)
    resource_needs = resource_requirement_facts(db, institute_id)
    employees = db.scalars(select(Employee).where(Employee.institute_id == institute_id)).all()
    sessions = db.scalars(select(ServiceSession).where(
        ServiceSession.institute_id == institute_id,
        ServiceSession.status.in_(ACTIVE_SESSION_STATUSES),
    )).all()
    appointments = db.scalars(select(Appointment).where(
        Appointment.institute_id == institute_id,
        Appointment.status.in_(ACTIVE_APPOINTMENT_STATUSES), Appointment.end_time > now,
    )).all()
    timelines = []
    for employee in employees:
        active = [session for session in sessions if session.employee_id == employee.id]
        if employee.status not in {"available", "busy"}:
            continue
        # An overdue service has no known remaining duration. Do not fabricate
        # immediate availability; finishing/extending it restores a projection.
        if any(aware(session.planned_end_time) <= now for session in active):
            continue
        booked = tuple((aware(appt.start_time), aware(appt.end_time))
                       for appt in appointments if appt.employee_id == employee.id)
        if employee.status == "busy" and not active and not any(start <= now < end for start, end in booked):
            continue
        available_from = max([now] + [aware(session.planned_end_time) for session in active])
        timelines.append(EmployeeTimeline(employee.id, available_from, booked, frozenset(qualifications.get(employee.id, set()))))
    tickets = db.scalars(select(QueueTicket).where(
        QueueTicket.institute_id == institute_id, QueueTicket.status.in_(["waiting", "assigned"]),
    ).order_by(QueueTicket.arrival_time, QueueTicket.id)).all()
    durations = {}
    ticket_skills = {}
    unknown_resource_tickets = set()
    for ticket_id, minutes, quantity, service_id in db.execute(select(
        TicketLine.ticket_id, TicketLine.duration_minutes, TicketLine.quantity, TicketLine.service_id,
    ).join(QueueTicket, QueueTicket.id == TicketLine.ticket_id).where(
        QueueTicket.institute_id == institute_id, QueueTicket.status.in_(["waiting", "assigned"]),
    )):
        durations[ticket_id] = durations.get(ticket_id, 0) + minutes * quantity
        ticket_skills.setdefault(ticket_id, set()).update(requirements.get(service_id, set()))
        if resource_needs.get(service_id):
            unknown_resource_tickets.add(ticket_id)
    queue = [QueueWork(ticket.id, durations.get(ticket.id, 0), ticket.assigned_employee_id,
                       frozenset(ticket_skills.get(ticket.id, set())), ticket.id not in unknown_resource_tickets)
             for ticket in tickets]
    if new_duration is not None:
        needed = set().union(*(requirements.get(service_id, set()) for service_id in new_service_ids or []))
        known_resources = not any(resource_needs.get(service_id) for service_id in new_service_ids or [])
        queue.append(QueueWork("__new_arrival__", new_duration, required_skills=frozenset(needed),
                              resource_capacity_known=known_resources))
    return project_queue(timelines, queue)
