"""Transactional reservation primitives. Callers retain the commit boundary."""
from datetime import timezone

from sqlalchemy import or_, select

from app.modules.appointments.models import Appointment
from app.modules.resources.allocation_domain import ResourceTimeline, match_resources
from app.modules.resources.models import Resource, ResourceReservation
from app.modules.tickets.models import QueueTicket
from app.modules.tickets.repository import lock_institute
from app.shared.exceptions import business_error, not_found
from app.shared.ids import new_id
from app.shared.time import utcnow


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def resource_timelines(db, institute_id, *, exclude_ticket_id=None, exclude_appointment_id=None, now=None):
    query = select(ResourceReservation).where(ResourceReservation.institute_id == institute_id,
                                              ResourceReservation.status != "released")
    if exclude_ticket_id:
        query = query.where(or_(ResourceReservation.ticket_id.is_(None), ResourceReservation.ticket_id != exclude_ticket_id))
    if exclude_appointment_id:
        query = query.where(or_(ResourceReservation.appointment_id.is_(None), ResourceReservation.appointment_id != exclude_appointment_id))
    rows = list(db.scalars(query).all())
    now = aware(now or utcnow())
    resources = db.scalars(select(Resource).where(Resource.institute_id == institute_id)
                          .execution_options(populate_existing=True)).all()
    return [ResourceTimeline(resource.id, resource.kind, frozenset(resource.capabilities),
        tuple((aware(row.start_time), aware(row.end_time)) for row in rows if row.resource_id == resource.id),
        resource.status == "active",
        not any(row.resource_id == resource.id and aware(row.end_time) <= now for row in rows))
        for resource in resources]


def _owner(db, institute_id, ticket_id, appointment_id):
    if (ticket_id is None) == (appointment_id is None):
        raise ValueError("Exactly one reservation owner is required")
    model, identifier = (QueueTicket, ticket_id) if ticket_id else (Appointment, appointment_id)
    owner = db.scalar(select(model).where(model.id == identifier, model.institute_id == institute_id))
    if owner is None:
        raise not_found("Reservation introuvable")
    return ResourceReservation.ticket_id == ticket_id if ticket_id else ResourceReservation.appointment_id == appointment_id


def reserve(db, institute_id, needs, start, end, *, ticket_id=None, appointment_id=None, in_use=False):
    lock_institute(db, institute_id)
    owner_filter = _owner(db, institute_id, ticket_id, appointment_id)
    start, end = aware(start), aware(end)
    existing = list(db.scalars(select(ResourceReservation).where(
        ResourceReservation.institute_id == institute_id, owner_filter,
        ResourceReservation.status != "released")).all())
    timelines = resource_timelines(db, institute_id, exclude_ticket_id=ticket_id,
                                   exclude_appointment_id=appointment_id)
    if any(row.status == "in_use" for row in existing):
        occupied = {row.resource_id for row in existing}
        timelines = [resource for resource in timelines if resource.resource_id in occupied]
    match = match_resources(timelines, needs, start, end)
    if match is None:
        raise business_error("Aucune combinaison de ressources disponible sur tout le creneau")
    selected = set(match.resource_ids)
    retained = set()
    for row in existing:
        if row.resource_id in selected and row.resource_id not in retained:
            row.start_time, row.end_time = start, end
            row.status = "in_use" if in_use else "reserved"
            retained.add(row.resource_id)
        else:
            row.status = "released"
    for resource_id in sorted(selected - retained):
        db.add(ResourceReservation(id=new_id("rrs"), institute_id=institute_id, resource_id=resource_id,
            ticket_id=ticket_id, appointment_id=appointment_id, start_time=start, end_time=end,
            status="in_use" if in_use else "reserved"))
    db.flush()
    return match


def release(db, institute_id, *, ticket_id=None, appointment_id=None):
    lock_institute(db, institute_id)
    owner_filter = _owner(db, institute_id, ticket_id, appointment_id)
    for row in db.scalars(select(ResourceReservation).where(ResourceReservation.institute_id == institute_id,
                          owner_filter, ResourceReservation.status != "released")):
        row.status = "released"
    db.flush()


def ticket_resource_needs(db, ticket):
    from app.modules.resources.allocation_domain import ResourceNeed
    from app.modules.resources.repository import resource_requirement_facts, ticket_services
    facts = resource_requirement_facts(db, ticket.institute_id)
    # One session performs the ticket's services sequentially. Reuse identical
    # requirements across services, while retaining the pool for the full session.
    quantities = {}
    for service_id in ticket_services(db, ticket.institute_id, ticket.id):
        for kind, capability, quantity in facts.get(service_id, []):
            key = (kind, capability)
            quantities[key] = max(quantities.get(key, 0), quantity)
    return [ResourceNeed(kind, capability, quantity) for (kind, capability), quantity in sorted(quantities.items())]


def reserve_ticket(db, ticket, start, end, *, in_use=False):
    needs = ticket_resource_needs(db, ticket)
    return reserve(db, ticket.institute_id, needs, start, end, ticket_id=ticket.id, in_use=in_use)


def appointment_resource_needs(db, institute_id, service_id):
    from app.modules.resources.allocation_domain import ResourceNeed
    from app.modules.resources.repository import resource_requirement_facts
    facts = resource_requirement_facts(db, institute_id)
    return [ResourceNeed(*need) for need in facts.get(service_id, [])]


def preview_appointment_resources(db, institute_id, service_id, start, end):
    lock_institute(db, institute_id)
    needs = appointment_resource_needs(db, institute_id, service_id)
    match = match_resources(resource_timelines(db, institute_id), needs, aware(start), aware(end))
    if match is None:
        raise business_error("Aucune combinaison de ressources disponible sur tout le creneau")
    return match


def reserve_appointment(db, appointment, start, end, *, in_use=False):
    needs = appointment_resource_needs(db, appointment.institute_id, appointment.service_id)
    return reserve(db, appointment.institute_id, needs, start, end,
                   appointment_id=appointment.id, in_use=in_use)
