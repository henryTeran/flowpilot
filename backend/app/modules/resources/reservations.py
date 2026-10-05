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
    owner_column = ResourceReservation.ticket_id if ticket_id else ResourceReservation.appointment_id
    other_owner = or_(owner_column.is_(None), owner_column != (ticket_id or appointment_id))
    others = list(db.scalars(select(ResourceReservation).where(
        ResourceReservation.institute_id == institute_id, other_owner,
        ResourceReservation.status != "released")).all())
    now = utcnow()
    resources = list(db.scalars(select(Resource).where(Resource.institute_id == institute_id)
                               .execution_options(populate_existing=True)).all())
    timelines = [ResourceTimeline(resource.id, resource.kind, frozenset(resource.capabilities),
        tuple((aware(row.start_time), aware(row.end_time)) for row in others if row.resource_id == resource.id),
        resource.status == "active",
        not any(row.resource_id == resource.id and aware(row.end_time) <= now for row in others))
        for resource in resources]
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
