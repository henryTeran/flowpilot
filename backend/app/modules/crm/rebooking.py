"""Read-only rebooking review using existing CRM event and appointment sources."""
from typing import Literal
from pydantic import AwareDatetime, model_validator
from sqlalchemy import select
from app.modules.appointments.models import Appointment
from app.modules.appointments.repository import ACTIVE_APPOINTMENT_STATUSES
from app.modules.crm import event_sources
from app.modules.crm.automation_policy import AutomationRule
from app.modules.crm.event_candidates import EventCandidate
from app.modules.crm.metrics import Count, Fact, Identifier
from app.modules.waitlist.originals import fingerprint
from app.shared.time import explicit_utc_instant


class Booking(Fact):
    appointment_id: Identifier
    service_id: Identifier
    start_at: AwareDatetime
    end_at: AwareDatetime
    status: Literal["scheduled", "confirmed", "arrived", "in_progress"]

    @model_validator(mode="after")
    def positive_slot(self):
        if not self.start_at < self.end_at:
            raise ValueError("Positive appointment slot required")
        return self


class RebookingRead(Fact):
    institute_id: Identifier
    customer_id: Identifier
    captured_at: AwareDatetime
    policy_original_id: Identifier | None
    policy_original_digest: str | None
    rule: AutomationRule | None
    candidate: EventCandidate | None
    active_bookings: tuple[Booking, ...]
    invalid_booking_count: Count
    diagnostics: dict[str, Count]
    review: Literal["available", "already_booked", "not_due", "disabled", "unavailable"]
    complete_customer_history: Literal[False] = False
    external_message_sent: Literal[False] = False
    delivery_authorized: Literal[False] = False
    execution_authorized: Literal[False] = False

    @model_validator(mode="after")
    def source_binding(self):
        if (self.policy_original_id is None) != (self.policy_original_digest is None):
            raise ValueError("Policy identity and digest must be present together")
        if self.rule is not None and (self.rule.trigger != "rebooking" or self.policy_original_id is None):
            raise ValueError("Only the recorded rebooking rule is admitted")
        candidate = self.candidate
        if candidate is not None and (
            candidate.institute_id != self.institute_id or candidate.customer_id != self.customer_id
            or candidate.policy_original_id != self.policy_original_id or candidate.rule != self.rule
            or candidate.captured_at != self.captured_at or candidate.source.source_kind != "care_episode"
            or candidate.source.institute_id != self.institute_id or candidate.source.customer_id != self.customer_id):
            raise ValueError("Rebooking candidate must match its selected source and capture")
        if any(b.end_at <= self.captured_at for b in self.active_bookings):
            raise ValueError("Only active observed bookings are admitted")
        expected = "unavailable"
        if candidate is not None and not self.invalid_booking_count:
            expected = {"scheduled": "not_due", "disabled": "disabled",
                "due": "already_booked" if self.active_bookings else "available"}.get(candidate.state, "unavailable")
        if self.review != expected:
            raise ValueError("Review label must match candidate and booking facts")
        return self


def read(db, institute, customer, *, _captured_at=None):
    # Existing reader locks the institute and requires the registered customer.
    source = event_sources.read(db, institute, customer, _captured_at=_captured_at)
    policy = source.policy_original
    rule = next((r for r in policy.policy.rules if r.trigger == "rebooking"), None) if policy else None
    candidate = next((c for c in source.candidates if c.rule.trigger == "rebooking"), None)
    rows = db.scalars(select(Appointment).where(Appointment.institute_id == institute,
        Appointment.customer_id == customer, Appointment.status.in_(ACTIVE_APPOINTMENT_STATUSES),
        Appointment.end_time > source.captured_at).order_by(Appointment.start_time, Appointment.id))
    bookings = []
    invalid = 0
    for row in rows:
        try:
            bookings.append(Booking(appointment_id=row.id, service_id=row.service_id,
                start_at=explicit_utc_instant(row.start_time), end_at=explicit_utc_instant(row.end_time), status=row.status))
        except (ValueError, TypeError):
            invalid += 1
    review = "unavailable"
    if candidate is not None and not invalid:
        review = {"scheduled": "not_due", "disabled": "disabled", "due": "already_booked" if bookings else "available"}.get(candidate.state, "unavailable")
    relevant = {k: v for k, v in source.diagnostics.items() if k in {
        "policy_absent", "future_policy", "future_registration", "care_unavailable", "care_unlinked_ticket",
        "care_invalid_owner_or_service", "care_invalid_actual_times", "invalid_event_timing"}}
    return RebookingRead(institute_id=institute, customer_id=customer, captured_at=source.captured_at,
        policy_original_id=policy.id if policy else None,
        policy_original_digest=fingerprint(policy.model_dump(mode="json")) if policy else None,
        rule=rule, candidate=candidate, active_bookings=tuple(bookings), invalid_booking_count=invalid,
        diagnostics=relevant, review=review)
