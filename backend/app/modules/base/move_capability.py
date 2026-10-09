"""Exact owned move preview using the existing booking/history/domain readers."""
from datetime import timezone, timedelta
from typing import Literal
from pydantic import AwareDatetime, field_validator, model_validator
from app.modules.base import read_capabilities as base, sensitive_capabilities as sensitive
from app.modules.base.plans import guard
from app.modules.crm.metrics import Fact, Count
from app.modules.customers.repository import require_customer
from app.modules.appointments.schemas import AppointmentUpdate
from app.modules.appointments.service import preview_update
from app.modules.waitlist.originals import fingerprint
from app.shared.time import utcnow
from app.shared.exceptions import business_error


class Capability(Fact):
    name: Literal["APPOINTMENT_MOVE"] = "APPOINTMENT_MOVE"
    prepare_level: Literal[2] = 2
    roles: tuple[Literal["responsable_institut"], ...] = ("responsable_institut",)
    application_service: Literal["appointments.service.preview_update"] = "appointments.service.preview_update"
    approval: Literal["explicit_human_approval_of_exact_retained_operation_required"] = "explicit_human_approval_of_exact_retained_operation_required"
    execution_registered: Literal[False, True] = True

    @field_validator("execution_registered", mode="before")
    @classmethod
    def captured_registration(cls, value):
        if type(value) is not bool:
            raise ValueError("An explicit captured registration flag is required")
        return value


CAPABILITY = Capability()


class Selection(Fact):
    appointment_id: base.ExactId
    start_time: AwareDatetime
    employee_id: base.ExactId | None = None
    service_id: base.ExactId | None = None

    @field_validator("start_time", mode="before")
    @classmethod
    def explicit_time(cls, value):
        if not isinstance(value, str) or "T" not in value:
            raise ValueError("An explicit aware ISO move instant is required")
        return value

    @field_validator("start_time")
    @classmethod
    def canonical_time(cls, value):
        return value.astimezone(timezone.utc)


def state_digest(institute, selection, appointment, proposed, history, count, resources):
    return fingerprint(dict(institute_id=institute, selection=selection.model_dump(mode="json"),
        appointment=appointment.model_dump(mode="json"), proposed=proposed.model_dump(mode="json"),
        booking_history_fingerprint=history, booking_events=count, resource_ids=resources))


class Preview(Fact):
    principal: base.Principal
    capability: Capability = CAPABILITY
    selection: Selection
    captured_at: AwareDatetime
    appointment: sensitive.Snapshot
    proposed: sensitive.Snapshot
    booking_events: Count
    booking_history_fingerprint: base.Digest
    resource_ids: tuple[base.ExactId, ...]
    state_fingerprint: base.Digest
    effect: Literal["move_preview_only_no_reservation_approval_or_execution"] = "move_preview_only_no_reservation_approval_or_execution"

    @model_validator(mode="after")
    def binding(self):
        before, after, selection = self.appointment, self.proposed, self.selection
        if (self.capability.model_dump(exclude={"execution_registered"}) != CAPABILITY.model_dump(exclude={"execution_registered"}) or self.principal.role.value not in self.capability.roles
            or self.captured_at.utcoffset() != timedelta(0) or before.status not in {"scheduled", "confirmed"}
            or before.actual_start_time is not None or before.actual_end_time is not None or before.checkout_ticket_id is not None
            or after.status != before.status or after.customer_id != before.customer_id
            or after.actual_start_time != before.actual_start_time or after.actual_end_time != before.actual_end_time
            or after.checkout_ticket_id != before.checkout_ticket_id or after.start_time != selection.start_time
            or after.employee_id != (selection.employee_id or before.employee_id)
            or after.service_id != (selection.service_id or before.service_id)
            or after.booked_start_time != after.start_time or after.booked_end_time != after.end_time
            or after.service_id == before.service_id and after.end_time-after.start_time != before.end_time-before.start_time
            or (after.start_time, after.employee_id, after.service_id) == (before.start_time, before.employee_id, before.service_id)
            or tuple(sorted(set(self.resource_ids))) != self.resource_ids
            or self.state_fingerprint != state_digest(self.principal.institute_id, selection, before, after,
                self.booking_history_fingerprint, self.booking_events, self.resource_ids)):
            raise ValueError("Exact signed source, changed target and scoped move projection required")
        return self


def preview(db, principal, institute, candidate):
    principal = guard(principal, institute)
    try:
        selection = Selection.model_validate(candidate.model_dump(mode="json") if isinstance(candidate, Selection) else candidate)
        source = sensitive.preview(db, principal, institute, {"appointment_id": selection.appointment_id})
        before = sensitive.Snapshot.model_validate(source.appointment)
        if before.customer_id is not None:
            require_customer(db, institute, before.customer_id)
        checked = preview_update(db, institute, selection.appointment_id,
            AppointmentUpdate(**selection.model_dump(exclude={"appointment_id"}, exclude_none=True)))
        if not checked.changed_slot or sensitive.Snapshot.model_validate(checked.before) != before:
            raise business_error("Move requires a changed target and unchanged reviewed source")
        proposed = sensitive.Snapshot.model_validate(checked.after)
        return Preview(principal=principal, selection=selection, captured_at=utcnow(), appointment=before, proposed=proposed,
            booking_events=source.booking_events, booking_history_fingerprint=source.booking_history_fingerprint,
            resource_ids=checked.resource_ids, state_fingerprint=state_digest(institute, selection, before, proposed,
                source.booking_history_fingerprint, source.booking_events, checked.resource_ids))
    except ValueError as error:
        raise business_error("Move preview sources require verification") from error
