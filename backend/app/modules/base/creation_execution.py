"""Creation effect/proof adapter inside the shared atomic execution transaction."""
from datetime import timedelta
from typing import Literal
from pydantic import AwareDatetime, model_validator
from sqlalchemy import select
from app.modules.base import executions, creation_capability as creation, sensitive_capabilities as sensitive
from app.modules.base.read_capabilities import ExactId, Actor, Digest
from app.modules.appointments.schemas import AppointmentCreate
from app.modules.appointments.service import create_appointment
from app.modules.appointments.events import snapshot
from app.modules.appointments.models import BookingEvent
from app.modules.resources.models import ResourceReservation
from app.modules.waitlist.originals import fingerprint
from app.shared.time import utcnow, explicit_utc_instant
from app.shared.ids import new_id
from app.shared.exceptions import business_error


class Result(sensitive.Snapshot):
    status: Literal["scheduled"]


def expected_snapshot(preview):
    selected = preview.selection
    return dict(status="scheduled", employee_id=selected.employee_id, service_id=selected.service_id,
        customer_id=selected.customer_id, start_time=selected.start_time, end_time=preview.end_time,
        booked_start_time=selected.start_time, booked_end_time=preview.end_time,
        actual_start_time=None, actual_end_time=None, checkout_ticket_id=None)


def metadata(value):
    return dict(customer_name=value.customer_name, phone=value.phone or None, notes=value.notes or None)


class Original(executions.Request):
    id: ExactId
    institute_id: ExactId
    actor_id: Actor
    created_at: AwareDatetime
    before: creation.Preview
    after: Result
    appointment_id: ExactId
    saved_metadata_digest: Digest
    booking_event_id: ExactId
    booking_event_fingerprint: Digest
    effect: Literal["appointment_created_through_existing_service_no_contact_or_payment"] = "appointment_created_through_existing_service_no_contact_or_payment"
    resource_basis: Literal["checked_and_reserved_in_execution_transaction_not_current_occupancy"] = "checked_and_reserved_in_execution_transaction_not_current_occupancy"

    @model_validator(mode="after")
    def exact_effect(self):
        if ((self.before.principal.actor_id, self.before.principal.institute_id) != (self.actor_id, self.institute_id)
            or self.created_at.utcoffset() != timedelta(0) or self.before.captured_at > self.created_at
            or self.after != Result.model_validate(expected_snapshot(self.before))
            or self.saved_metadata_digest != fingerprint(metadata(self.before.selection))):
            raise ValueError("Exact signed creation effect and reviewed metadata required")
        for value in (self.id, self.appointment_id, self.booking_event_id):
            if value != value.strip() or any(ord(c) < 32 for c in value):
                raise ValueError("Exact execution/booking/event identity required")
        return self


def perform(db, principal, request, preview):
    # Common execution lock/approval/version checks precede this; no inner commit.
    appointment = create_appointment(db, AppointmentCreate(institute_id=principal.institute_id,
        **preview.selection.model_dump()), principal.actor_id, commit=False)
    result = Result.model_validate(snapshot(appointment))
    if result != Result.model_validate(expected_snapshot(preview)) or metadata(appointment) != metadata(preview.selection):
        raise business_error("Created booking must match every exact approved term")
    reservations = list(db.scalars(select(ResourceReservation).where(
        ResourceReservation.institute_id == principal.institute_id, ResourceReservation.appointment_id == appointment.id,
        ResourceReservation.status != "released")))
    if (tuple(sorted(row.resource_id for row in reservations)) != preview.resource_ids
        or any(row.status != "reserved" or explicit_utc_instant(row.start_time) != preview.selection.start_time
            or explicit_utc_instant(row.end_time) != preview.end_time for row in reservations)):
        raise business_error("Creation must reserve the exact checked interval and resources")
    events = list(db.scalars(select(BookingEvent).where(BookingEvent.institute_id == principal.institute_id,
        BookingEvent.appointment_id == appointment.id)))
    if len(events) != 1:
        raise business_error("Creation must produce exactly one original booking event")
    return Original(**request.model_dump(), id=new_id("base_execution"), institute_id=principal.institute_id,
        actor_id=principal.actor_id, created_at=utcnow(), before=preview, after=result, appointment_id=appointment.id,
        saved_metadata_digest=fingerprint(metadata(appointment)), booking_event_id=events[0].id,
        booking_event_fingerprint=fingerprint(executions.event_raw(events[0])))
