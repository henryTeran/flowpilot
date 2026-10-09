"""Move effect/proof adapter inside the common execution transaction."""
from datetime import timedelta
from typing import Literal
from pydantic import AwareDatetime, model_validator
from sqlalchemy import select
from app.modules.base import executions, move_capability as move, sensitive_capabilities as sensitive
from app.modules.base.creation_execution import metadata
from app.modules.base.read_capabilities import ExactId, Actor, Digest
from app.modules.appointments.models import Appointment, BookingEvent
from app.modules.appointments.schemas import AppointmentUpdate
from app.modules.appointments.service import update_appointment
from app.modules.appointments.events import snapshot
from app.modules.resources.models import ResourceReservation
from app.modules.waitlist.originals import fingerprint
from app.shared.time import utcnow, explicit_utc_instant
from app.shared.ids import new_id
from app.shared.exceptions import business_error


class Original(executions.Request):
    id: ExactId
    institute_id: ExactId
    actor_id: Actor
    created_at: AwareDatetime
    before: move.Preview
    after: sensitive.Snapshot
    appointment_id: ExactId
    before_metadata_digest: Digest
    after_metadata_digest: Digest
    booking_event_id: ExactId
    booking_event_fingerprint: Digest
    effect: Literal["appointment_moved_through_existing_service_no_contact_or_payment"] = "appointment_moved_through_existing_service_no_contact_or_payment"
    resource_basis: Literal["checked_and_reserved_in_execution_transaction_not_current_occupancy"] = "checked_and_reserved_in_execution_transaction_not_current_occupancy"

    @model_validator(mode="after")
    def exact_effect(self):
        if ((self.before.principal.actor_id, self.before.principal.institute_id) != (self.actor_id, self.institute_id)
            or self.created_at.utcoffset() != timedelta(0) or self.before.captured_at > self.created_at
            or self.appointment_id != self.before.selection.appointment_id or self.after != self.before.proposed
            or self.before_metadata_digest != self.after_metadata_digest):
            raise ValueError("Exact signed move effect with unchanged customer metadata required")
        for value in (self.id, self.appointment_id, self.booking_event_id):
            if value != value.strip() or any(ord(c) < 32 for c in value):
                raise ValueError("Exact execution/booking/event identity required")
        return self


def perform(db, principal, request, preview):
    identifier = preview.selection.appointment_id
    appointment = db.scalar(select(Appointment).where(Appointment.institute_id == principal.institute_id,
        Appointment.id == identifier).execution_options(populate_existing=True))
    if appointment is None or sensitive.Snapshot.model_validate(snapshot(appointment)) != preview.appointment:
        raise business_error("Move source must still match the approved booking")
    before_metadata = metadata(appointment)
    event_ids = set(db.scalars(select(BookingEvent.id).where(BookingEvent.institute_id == principal.institute_id,
        BookingEvent.appointment_id == identifier)))
    if len(event_ids) != preview.booking_events:
        raise business_error("Move source history must remain unchanged")
    appointment = update_appointment(db, identifier, AppointmentUpdate(**preview.selection.model_dump(
        exclude={"appointment_id"}, exclude_none=True)), principal.actor_id, commit=False)
    result = sensitive.Snapshot.model_validate(snapshot(appointment))
    if result != preview.proposed or metadata(appointment) != before_metadata:
        raise business_error("Moved booking must match the approved target and preserve customer metadata")
    reservations = list(db.scalars(select(ResourceReservation).where(ResourceReservation.institute_id == principal.institute_id,
        ResourceReservation.appointment_id == identifier, ResourceReservation.status != "released")))
    if (tuple(sorted(row.resource_id for row in reservations)) != preview.resource_ids
        or any(row.status != "reserved" or explicit_utc_instant(row.start_time) != result.start_time
            or explicit_utc_instant(row.end_time) != result.end_time for row in reservations)):
        raise business_error("Move must reserve the exact approved interval and resources")
    events = [row for row in db.scalars(select(BookingEvent).where(BookingEvent.institute_id == principal.institute_id,
        BookingEvent.appointment_id == identifier)) if row.id not in event_ids]
    if len(events) != 1:
        raise business_error("Move must produce exactly one modification event")
    return Original(**request.model_dump(), id=new_id("base_execution"), institute_id=principal.institute_id,
        actor_id=principal.actor_id, created_at=utcnow(), before=preview, after=result, appointment_id=identifier,
        before_metadata_digest=fingerprint(before_metadata), after_metadata_digest=fingerprint(metadata(appointment)),
        booking_event_id=events[0].id, booking_event_fingerprint=fingerprint(executions.event_raw(events[0])))
