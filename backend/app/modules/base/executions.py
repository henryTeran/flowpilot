"""Closed atomic booking executors, after exact approval and current reread."""
from datetime import timedelta, timezone
from types import MappingProxyType
from typing import Literal
from pydantic import AwareDatetime, model_validator
from sqlalchemy import select
from app.modules.base import read_capabilities as base, approvals, sensitive_originals as operations, sensitive_capabilities as sensitive
from app.modules.base.plans import Key, Reason, guard
from app.modules.base.models import ExecutionOriginal
from app.modules.appointments.models import BookingEvent
from app.modules.appointments.events import snapshot
from app.modules.appointments.service import cancel_appointment
from app.modules.crm.metrics import Fact
from app.modules.waitlist.originals import Envelope, fingerprint
from app.modules.tickets.repository import lock_institute
from app.shared.time import utcnow, explicit_utc_instant
from app.shared.ids import new_id
from app.shared.exceptions import business_error


class Capability(Fact):
    name: Literal["APPOINTMENT_CANCEL", "APPOINTMENT_CREATE"] = "APPOINTMENT_CANCEL"
    level: Literal[3] = 3
    roles: tuple[Literal["responsable_institut"], ...] = ("responsable_institut",)
    authority: Literal["exact_retained_operation_latest_approval_future_validity_fresh_source"] = "exact_retained_operation_latest_approval_future_validity_fresh_source"
    service: Literal["appointments.service.cancel_appointment_commit_false", "appointments.service.create_appointment_commit_false"] = "appointments.service.cancel_appointment_commit_false"


REGISTRY = MappingProxyType({"APPOINTMENT_CANCEL": Capability(), "APPOINTMENT_CREATE": Capability(
    name="APPOINTMENT_CREATE", service="appointments.service.create_appointment_commit_false")})


class Request(Fact):
    operation_id: base.ExactId
    operation_fingerprint: base.Digest
    approval_id: base.ExactId
    approval_fingerprint: base.Digest
    reason: Reason
    idempotency_key: Key

    @model_validator(mode="after")
    def exact_terms(self):
        if any(v != v.strip() or any(ord(c) < 32 for c in v) for v in (self.operation_id, self.approval_id, self.reason, self.idempotency_key)):
            raise ValueError("Exact execution references, reason and key required")
        return self


class Result(sensitive.Snapshot):
    status: Literal["cancelled"]


class Original(Request):
    id: base.ExactId
    institute_id: base.ExactId
    actor_id: base.Actor
    created_at: AwareDatetime
    before: sensitive.Preview
    after: Result
    booking_event_id: base.ExactId
    booking_event_fingerprint: base.Digest
    effect: Literal["appointment_cancelled_through_existing_service_no_contact_or_refund"] = "appointment_cancelled_through_existing_service_no_contact_or_refund"

    @model_validator(mode="after")
    def exact_effect(self):
        if (self.before.principal.actor_id, self.before.principal.institute_id) != (self.actor_id, self.institute_id) or \
                self.created_at.utcoffset() != timedelta(0) or self.before.captured_at > self.created_at or \
                self.after.model_dump(mode="json") != {**self.before.appointment, "status": "cancelled"}:
            raise ValueError("Execution must retain its signed exact cancellation effect and clock")
        if any(v != v.strip() or any(ord(c) < 32 for c in v) for v in (self.id, self.booking_event_id)):
            raise ValueError("Exact execution/event identity required")
        return self


def event_raw(event):
    return dict(id=event.id, institute_id=event.institute_id, appointment_id=event.appointment_id,
        event_type=event.event_type, actor_id=event.actor_id, occurred_at=explicit_utc_instant(event.occurred_at).astimezone(timezone.utc).isoformat(),
        before=event.before, after=event.after, price_reference=event.price_reference)


def verify(db, principal, institute, row, now):
    from app.modules.base import creation_execution as creation
    try:
        if not isinstance(row.original, dict) or row.institute_id != institute or fingerprint(row.original) != row.fingerprint:
            raise ValueError("Execution ownership/raw SHA mismatch")
        is_creation = row.original.get("effect") == "appointment_created_through_existing_service_no_contact_or_payment"
        original = (creation.Original if is_creation else Original).model_validate(row.original)
        if original.model_dump(mode="json") != row.original or \
                (original.id, original.institute_id, original.operation_id, original.approval_id, original.booking_event_id,
                 original.idempotency_key, original.actor_id, original.created_at) != \
                (row.id, institute, row.operation_id, row.approval_id, row.booking_event_id, row.idempotency_key,
                 row.actor_id, explicit_utc_instant(row.created_at)) or original.created_at > now:
            raise ValueError("Canonical execution columns/clock mismatch")
        state = approvals.state(db, principal, institute, original.operation_id, _now=now)
        operation = operations.Original.model_validate(state.operation.original)
        if operation.capability != ("APPOINTMENT_CREATE" if is_creation else "APPOINTMENT_CANCEL"):
            raise ValueError("Execution receipt must match the operation capability")
        if is_creation and original.before.selection != operation.selection:
            raise ValueError("Creation receipt must retain the exact prepared selection")
        approval = next((v for v in state.decisions if v.original["id"] == original.approval_id), None)
        if state.operation.fingerprint != original.operation_fingerprint or approval is None or \
                approval.fingerprint != original.approval_fingerprint or approval.original["decision"] != "approve" or \
                state.status != "approved" or original.before.state_fingerprint != operation.expected_state_fingerprint or \
                not approvals.Original.model_validate(approval.original).created_at <= original.before.captured_at <= original.created_at < operation.valid_until:
            raise ValueError("Execution requires its exact historical approved operation and validity")
        event = db.scalar(select(BookingEvent).where(BookingEvent.id == original.booking_event_id,
            BookingEvent.institute_id == institute, BookingEvent.appointment_id == (original.appointment_id if is_creation else operation.selection.appointment_id))
            .execution_options(populate_existing=True))
        if event is None or event.event_type != ("created" if is_creation else "cancelled") or event.actor_id != original.actor_id or \
                fingerprint(event_raw(event)) != original.booking_event_fingerprint or explicit_utc_instant(event.occurred_at) > original.created_at or \
                (is_creation and explicit_utc_instant(event.occurred_at) < original.before.captured_at) or \
                (event.before is not None if is_creation else sensitive.Snapshot.model_validate(event.before).model_dump(mode="json") != original.before.appointment) or \
                (creation.Result if is_creation else Result).model_validate(event.after) != original.after:
            raise ValueError("Execution booking-event proof requires verification")
        return Envelope(original=row.original, fingerprint=row.fingerprint)
    except (ValueError, TypeError, KeyError, OverflowError, StopIteration) as error:
        raise business_error("Retained BASE execution requires verification") from error


def execute(db, principal, institute, candidate):
    try:
        principal = guard(principal, institute)
        request = Request.model_validate(candidate.model_dump() if isinstance(candidate, Request) else candidate)
        lock_institute(db, institute)
        old = db.scalar(select(ExecutionOriginal).where(ExecutionOriginal.institute_id == institute,
            ExecutionOriginal.idempotency_key == request.idempotency_key).execution_options(populate_existing=True))
        if old:
            receipt = verify(db, principal, institute, old, utcnow())
            if Request(**{k: receipt.original[k] for k in Request.model_fields}) != request or receipt.original["actor_id"] != principal.actor_id:
                raise business_error("Execution key retains the original terms and actor")
            return receipt
        if db.scalar(select(ExecutionOriginal.id).where(ExecutionOriginal.institute_id == institute,
                ExecutionOriginal.operation_id == request.operation_id)) is not None:
            raise business_error("Operation already performed; recover the original execution")
        state = approvals.state(db, principal, institute, request.operation_id)
        last = state.decisions[-1] if state.decisions else None
        if state.status != "approved" or state.expired or request.operation_fingerprint != state.operation.fingerprint or \
                last is None or (request.approval_id, request.approval_fingerprint) != (last.original["id"], last.fingerprint):
            raise business_error("Execution requires the exact current approved operation")
        operation = operations.Original.model_validate(state.operation.original)
        if operation.capability not in REGISTRY:
            raise business_error("Execution is not registered for this preparation capability")
        before = operations.current_preview(db, principal, institute, operation)
        if before.state_fingerprint != operation.expected_state_fingerprint or utcnow() >= operation.valid_until:
            raise business_error("Changed or expired operation cannot execute")
        if operation.capability == "APPOINTMENT_CREATE":
            from app.modules.base import creation_execution as creation
            original = creation.perform(db, principal, request, before)
        else:
            original = perform_cancellation(db, principal, institute, request, operation, before)
        if original.created_at >= operation.valid_until:
            raise business_error("Operation validity elapsed before execution confirmation")
        raw = original.model_dump(mode="json")
        row = ExecutionOriginal(id=original.id, institute_id=institute, operation_id=request.operation_id,
            approval_id=request.approval_id, booking_event_id=original.booking_event_id, actor_id=principal.actor_id,
            idempotency_key=request.idempotency_key, created_at=original.created_at, original=raw, fingerprint=fingerprint(raw))
        db.add(row); db.flush()
        receipt = verify(db, principal, institute, row, original.created_at)
        db.commit()
        return receipt
    except ValueError as error:
        db.rollback()
        raise business_error("BASE execution requires valid explicit terms") from error
    except Exception:
        db.rollback()
        raise


def perform_cancellation(db, principal, institute, request, operation, before):
    event_ids = set(db.scalars(select(BookingEvent.id).where(BookingEvent.institute_id == institute,
        BookingEvent.appointment_id == operation.selection.appointment_id)))
    appointment = cancel_appointment(db, operation.selection.appointment_id, principal.actor_id, commit=False)
    events = [v for v in db.scalars(select(BookingEvent).where(BookingEvent.institute_id == institute,
        BookingEvent.appointment_id == appointment.id)) if v.id not in event_ids]
    if len(events) != 1:
        raise business_error("Cancellation must produce one exact booking event")
    now = utcnow()
    if now >= operation.valid_until:
        raise business_error("Operation validity elapsed before execution confirmation")
    return Original(**request.model_dump(), id=new_id("base_execution"), institute_id=institute,
        actor_id=principal.actor_id, created_at=now, before=before, after=Result.model_validate(snapshot(appointment)),
        booking_event_id=events[0].id, booking_event_fingerprint=fingerprint(event_raw(events[0])))


def by_key(db, principal, institute, key):
    principal = guard(principal, institute)
    if not isinstance(key, str) or not key or len(key) > 120 or key != key.strip() or any(ord(c) < 32 for c in key):
        raise business_error("Exact execution recovery key required")
    lock_institute(db, institute)
    row = db.scalar(select(ExecutionOriginal).where(ExecutionOriginal.institute_id == institute,
        ExecutionOriginal.idempotency_key == key).execution_options(populate_existing=True))
    return verify(db, principal, institute, row, utcnow()) if row else None


def for_operation(db, principal, institute, identifier):
    principal = guard(principal, institute)
    operations.require(db, principal, institute, identifier)
    row = db.scalar(select(ExecutionOriginal).where(ExecutionOriginal.institute_id == institute,
        ExecutionOriginal.operation_id == identifier).execution_options(populate_existing=True))
    return verify(db, principal, institute, row, utcnow()) if row else None
