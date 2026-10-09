"""FlowPilot-owned exact creation preview, without reservation or approval."""
from datetime import timezone, timedelta
from typing import Annotated, Literal
from pydantic import AwareDatetime, StringConstraints, field_validator, model_validator
from app.modules.base import read_capabilities as base
from app.modules.base.plans import guard
from app.modules.crm.metrics import Fact
from app.modules.appointments.schemas import AppointmentCreate
from app.modules.appointments.service import preview_creation
from app.modules.waitlist.originals import fingerprint
from app.shared.time import utcnow


class Capability(Fact):
    name: Literal["APPOINTMENT_CREATE"] = "APPOINTMENT_CREATE"
    prepare_level: Literal[2] = 2
    roles: tuple[Literal["responsable_institut"], ...] = ("responsable_institut",)
    application_service: Literal["appointments.service.preview_creation"] = "appointments.service.preview_creation"
    approval: Literal["explicit_human_approval_of_exact_retained_operation_required"] = "explicit_human_approval_of_exact_retained_operation_required"
    execution_registered: Literal[False] = False


CAPABILITY = Capability()


class Selection(Fact):
    employee_id: base.ExactId
    service_id: base.ExactId
    customer_id: base.ExactId | None = None
    customer_name: Annotated[str, StringConstraints(strict=True, min_length=2, max_length=160)]
    phone: Annotated[str, StringConstraints(strict=True, max_length=40)] | None = None
    notes: Annotated[str, StringConstraints(strict=True, max_length=500)] | None = None
    start_time: AwareDatetime

    @field_validator("start_time", mode="before")
    @classmethod
    def explicit_time(cls, value):
        if not isinstance(value, str) or "T" not in value:
            # Rehydrate at application boundaries through JSON before validation.
            raise ValueError("An explicit aware ISO booking instant is required")
        return value

    @field_validator("start_time")
    @classmethod
    def canonical_time(cls, value):
        return value.astimezone(timezone.utc)

    @field_validator("customer_name", "phone", "notes")
    @classmethod
    def exact_text(cls, value):
        if value is not None and (value != value.strip() or any(ord(c) < 32 for c in value)):
            raise ValueError("Exact reviewed booking text is required")
        return value


def state_digest(institute, selection, end_time, resource_ids):
    return fingerprint(dict(institute_id=institute, selection=selection.model_dump(mode="json"),
        end_time=end_time.astimezone(timezone.utc).isoformat(), resource_ids=resource_ids))


class Preview(Fact):
    principal: base.Principal
    capability: Capability = CAPABILITY
    selection: Selection
    captured_at: AwareDatetime
    end_time: AwareDatetime
    resource_ids: tuple[base.ExactId, ...]
    state_fingerprint: base.Digest
    basis: Literal["exact_creation_terms_and_current_eligible_interval_resources_not_full_database_digest"] = "exact_creation_terms_and_current_eligible_interval_resources_not_full_database_digest"
    effect: Literal["creation_preview_only_no_reservation_approval_or_execution"] = "creation_preview_only_no_reservation_approval_or_execution"

    @model_validator(mode="after")
    def binding(self):
        if (self.principal.role.value not in self.capability.roles or self.capability != CAPABILITY
            or self.captured_at.utcoffset() != timedelta(0) or self.end_time.utcoffset() != timedelta(0)
            or self.end_time <= self.selection.start_time or tuple(sorted(set(self.resource_ids))) != self.resource_ids
            or self.state_fingerprint != state_digest(self.principal.institute_id, self.selection, self.end_time, self.resource_ids)):
            raise ValueError("Exact signed creation projection required")
        return self


def preview(db, principal, institute, candidate):
    principal = guard(principal, institute)
    selection = Selection.model_validate(candidate.model_dump(mode="json") if isinstance(candidate, Selection) else candidate)
    payload = AppointmentCreate(institute_id=institute, **selection.model_dump())
    match = preview_creation(db, payload)
    return Preview(principal=principal, selection=selection, captured_at=utcnow(), end_time=match.end,
        resource_ids=match.resource_ids, state_fingerprint=state_digest(institute, selection, match.end, match.resource_ids))
