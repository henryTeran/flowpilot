"""Closed sensitive preparation registry; no public executor or implicit approval."""
from types import MappingProxyType
from datetime import timedelta, datetime, timezone
from typing import Literal
from pydantic import AwareDatetime, model_validator, field_validator
from sqlalchemy import select
from app.modules.base import read_capabilities as base
from app.modules.crm.metrics import Fact, Count
from app.modules.appointments.models import Appointment, BookingEvent
from app.modules.appointments.events import snapshot
from app.modules.appointments.service import require_cancellable_source
from app.modules.waitlist.originals import fingerprint
from app.modules.tickets.repository import lock_institute
from app.shared.exceptions import not_found, business_error
from app.shared.time import utcnow, explicit_utc_instant


class Capability(Fact):
    name: Literal["APPOINTMENT_CANCEL"] = "APPOINTMENT_CANCEL"
    prepare_level: Literal[2] = 2
    execution_level: Literal[3] = 3
    roles: tuple[Literal["responsable_institut"], ...] = ("responsable_institut",)
    application_service: Literal["appointments.service.cancel_appointment"] = "appointments.service.cancel_appointment"
    approval: Literal["explicit_human_approval_of_exact_retained_operation_required"] = "explicit_human_approval_of_exact_retained_operation_required"
    public_execution: Literal[False] = False


REGISTRY = MappingProxyType({"APPOINTMENT_CANCEL": Capability()})


class Selection(Fact):
    appointment_id: base.ExactId


class Snapshot(Fact):
    status: Literal["scheduled", "confirmed", "arrived"]
    employee_id: base.ExactId
    service_id: base.ExactId
    customer_id: base.ExactId | None
    start_time: base.matching.Horizon
    end_time: base.matching.Horizon
    booked_start_time: base.matching.Horizon | None
    booked_end_time: base.matching.Horizon | None
    actual_start_time: base.matching.Horizon | None
    actual_end_time: base.matching.Horizon | None
    checkout_ticket_id: base.ExactId | None

    @field_validator("start_time", "end_time", "booked_start_time", "booked_end_time", "actual_start_time", "actual_end_time")
    @classmethod
    def canonical_source_time(cls, value):
        # SQL timestamptz may be returned in the connection's local timezone.
        return value.astimezone(timezone.utc) if isinstance(value, datetime) else value

    @model_validator(mode="after")
    def positive_interval(self):
        if self.end_time <= self.start_time:
            raise ValueError("A positive recorded appointment interval is required")
        if any(value is not None and value.utcoffset() != timedelta(0) for value in
                (self.start_time, self.end_time, self.booked_start_time, self.booked_end_time, self.actual_start_time, self.actual_end_time)):
            raise ValueError("Captured appointment instants must be canonical UTC")
        return self


def state_digest(institute, appointment_id, appointment, booking_events, history_hash):
    return fingerprint(dict(institute_id=institute, appointment_id=appointment_id,
        appointment=appointment, booking_events=booking_events, booking_history_fingerprint=history_hash))


class Preview(Fact):
    principal: base.Principal
    capability: Capability
    appointment_id: base.ExactId
    captured_at: AwareDatetime
    appointment: dict
    booking_events: Count
    booking_history_fingerprint: base.Digest
    state_fingerprint: base.Digest
    effect: Literal["cancellation_preview_only_no_approval_or_execution"] = "cancellation_preview_only_no_approval_or_execution"

    @model_validator(mode="after")
    def bound_snapshot(self):
        value = Snapshot.model_validate(self.appointment)
        if self.captured_at.utcoffset() != timedelta(0) or value.model_dump(mode="json") != self.appointment or self.capability != REGISTRY["APPOINTMENT_CANCEL"] or \
                self.principal.role.value not in self.capability.roles or self.state_fingerprint != state_digest(
                    self.principal.institute_id, self.appointment_id, self.appointment, self.booking_events, self.booking_history_fingerprint):
            raise ValueError("Cancellation preview must preserve the complete canonical scoped snapshot")
        return self


def capabilities(principal, institute):
    # Current sensitive adapter intentionally uses the existing manager-only scope.
    principal = base.authorize(principal, institute, "WAITLIST_READ")[0]
    return tuple(c for c in REGISTRY.values() if principal.role.value in c.roles)


def preview(db, principal, institute, candidate):
    principal = base.authorize(principal, institute, "WAITLIST_READ")[0]
    try:
        selection = Selection.model_validate(candidate.model_dump() if isinstance(candidate, Selection) else candidate)
    except (ValueError, TypeError) as error:
        raise business_error("An explicit owned appointment selection is required") from error
    lock_institute(db, institute)
    appointment = db.scalar(select(Appointment).where(Appointment.institute_id == institute,
        Appointment.id == selection.appointment_id).execution_options(populate_existing=True))
    if appointment is None:
        raise not_found("Owned cancellation appointment not found")
    require_cancellable_source(db, appointment)
    now, history = utcnow(), []
    for event in db.scalars(select(BookingEvent).where(BookingEvent.institute_id == institute,
            BookingEvent.appointment_id == appointment.id).order_by(BookingEvent.occurred_at, BookingEvent.id)
            .execution_options(populate_existing=True)):
        at = explicit_utc_instant(event.occurred_at).astimezone(timezone.utc)
        if at > now:
            raise business_error("Cancellation history contains a future event")
        history.append(dict(id=event.id, event_type=event.event_type, actor_id=event.actor_id,
            occurred_at=at.isoformat(), before=event.before, after=event.after, price_reference=event.price_reference))
    try:
        state, history_hash = Snapshot.model_validate(snapshot(appointment)).model_dump(mode="json"), fingerprint(history)
        digest = state_digest(institute, appointment.id, state, len(history), history_hash)
        return Preview(principal=principal, capability=REGISTRY["APPOINTMENT_CANCEL"], appointment_id=appointment.id,
            captured_at=now, appointment=state, booking_events=len(history), booking_history_fingerprint=history_hash,
            state_fingerprint=digest)
    except ValueError as error:
        raise business_error("Cancellation preview source requires verification") from error
