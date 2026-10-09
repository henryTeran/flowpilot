"""Read-only overlap evidence for one explicitly selected institute resource."""
from datetime import date
from typing import Literal
from pydantic import AwareDatetime
from sqlalchemy import select
from app.modules.resources.models import Resource, ResourceReservation
from app.modules.appointments.models import Appointment
from app.modules.tickets.models import QueueTicket
from app.modules.tickets.repository import lock_institute
from app.modules.institutes.calendar import day_bounds
from app.modules.workforce.conflicts import Commitment, Overlap, overlaps
from app.modules.crm.metrics import Fact, Identifier, Count
from app.modules.waitlist.originals import fingerprint
from app.shared.exceptions import business_error, not_found
from app.shared.time import explicit_utc_instant, utcnow


class Read(Fact):
    institute_id: Identifier
    resource_id: Identifier
    day: date
    captured_at: AwareDatetime
    start_at: AwareDatetime
    end_at: AwareDatetime
    resource_status: Literal["active", "inactive", "maintenance"]
    source_digest: str
    source_count: Count
    invalid_source_count: Count
    overdue_unreleased_source_count: Count
    overlap_count: Count
    overlaps: tuple[Overlap, ...]
    page_limit: Literal[50] = 50
    basis: Literal["current_unreleased_resource_reservations_half_open"] = "current_unreleased_resource_reservations_half_open"
    complete_institute_conflict_coverage: Literal[False] = False
    physical_activity_proven: Literal[False] = False
    booking_authorized: Literal[False] = False


def read(db, institute, resource, day):
    lock_institute(db, institute)
    owned = db.scalar(select(Resource).where(Resource.id == resource, Resource.institute_id == institute))
    if owned is None:
        raise not_found("Selected resource not found")
    start, end = day_bounds(db, institute, day)
    captured = utcnow()
    ticket_owned = select(QueueTicket.id).where(QueueTicket.id == ResourceReservation.ticket_id,
        QueueTicket.institute_id == institute).exists()
    appointment_owned = select(Appointment.id).where(Appointment.id == ResourceReservation.appointment_id,
        Appointment.institute_id == institute).exists()
    statement = select(ResourceReservation, ticket_owned, appointment_owned).where(
        ResourceReservation.institute_id == institute, ResourceReservation.resource_id == resource,
        ResourceReservation.status != "released")
    sources = []
    invalid = overdue = scanned = 0
    for row, ticket, appointment in db.execute(statement.execution_options(yield_per=100)):
        scanned += 1
        if scanned > 1000:
            raise business_error("Resource reservation capture exceeds supported source bound")
        if (row.ticket_id is None) == (row.appointment_id is None) or not (ticket or appointment):
            invalid += 1
            continue
        try:
            source = Commitment(kind="reservation", id=row.id, start_at=explicit_utc_instant(row.start_time),
                end_at=explicit_utc_instant(row.end_time))
        except (ValueError, TypeError):
            invalid += 1
            continue
        # Existing allocation treats every expired unreleased reservation as unknown.
        overdue += int(source.end_at <= captured)
        if source.start_at < end and source.end_at > start:
            sources.append(source)
    sources.sort(key=lambda s: (s.start_at, s.kind, s.id))
    total = 0
    page = []
    for overlap in overlaps(sources, start, end):
        total += 1
        if len(page) < 50:
            page.append(overlap)
    return Read(institute_id=institute, resource_id=resource, day=day, captured_at=captured, start_at=start, end_at=end,
        resource_status=owned.status, source_count=len(sources), source_digest=fingerprint([s.model_dump(mode="json") for s in sources]),
        invalid_source_count=invalid, overdue_unreleased_source_count=overdue, overlap_count=total, overlaps=tuple(page))
