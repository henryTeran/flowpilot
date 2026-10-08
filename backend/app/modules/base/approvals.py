"""Explicit signed decisions on an exact retained operation; never execution."""
from datetime import timedelta
from typing import Literal
from pydantic import AwareDatetime, model_validator
from sqlalchemy import select
from app.modules.base import read_capabilities as base, sensitive_originals as operations, sensitive_capabilities as sensitive
from app.modules.base.models import ApprovalOriginal, ExecutionOriginal
from app.modules.base.plans import Key, Reason, guard
from app.modules.crm.metrics import Fact
from app.modules.waitlist.originals import Envelope, fingerprint
from app.modules.tickets.repository import lock_institute
from app.shared.time import utcnow, explicit_utc_instant
from app.shared.ids import new_id
from app.shared.exceptions import business_error


class Request(Fact):
    operation_id: base.ExactId
    operation_fingerprint: base.Digest
    previous_id: base.ExactId | None
    previous_fingerprint: base.Digest | None
    decision: Literal["approve", "decline", "revoke"]
    reason: Reason
    idempotency_key: Key

    @model_validator(mode="after")
    def explicit_terms(self):
        if (self.previous_id is None) != (self.previous_fingerprint is None) or \
                any(v != v.strip() or any(ord(c) < 32 for c in v) for v in (self.reason, self.idempotency_key, self.operation_id, self.previous_id or "")):
            raise ValueError("Exact operation, paired predecessor and explicit decision terms required")
        return self


class Original(Request):
    id: base.ExactId
    institute_id: base.ExactId
    actor_id: base.Actor
    created_at: AwareDatetime
    source_checked_at: AwareDatetime | None
    checked_state_fingerprint: base.Digest | None
    effect: Literal["explicit_signed_human_decision_only_no_execution"] = "explicit_signed_human_decision_only_no_execution"

    @model_validator(mode="after")
    def coherent(self):
        if any(v != v.strip() or any(ord(c) < 32 for c in v) for v in (self.id, self.institute_id, self.actor_id)) or \
                self.id == self.previous_id or self.created_at.utcoffset() != timedelta(0):
            raise ValueError("Exact decision identity and UTC server clock required")
        if self.decision == "approve":
            if self.source_checked_at is None or self.checked_state_fingerprint is None or self.source_checked_at > self.created_at or self.source_checked_at.utcoffset() != timedelta(0):
                raise ValueError("Approval requires a recorded current-source check")
        elif self.source_checked_at is not None or self.checked_state_fingerprint is not None:
            raise ValueError("Stopping decisions must not invent a source check")
        return self


class State(Fact):
    operation: Envelope
    captured_at: AwareDatetime
    decisions: tuple[Envelope, ...]
    status: Literal["pending", "approved", "declined", "revoked"]
    expired: bool
    execution: Literal["not_performed_by_approval_manager"] = "not_performed_by_approval_manager"
    current_source: Literal["not_revalidated_by_historical_state_read"] = "not_revalidated_by_historical_state_read"


def verify(row, institute, now):
    try:
        if row.institute_id != institute or fingerprint(row.original) != row.fingerprint:
            raise ValueError("Decision ownership or raw SHA mismatch")
        original = Original.model_validate(row.original)
        if original.model_dump(mode="json") != row.original or \
                (original.id, original.institute_id, original.operation_id, original.previous_id, original.idempotency_key, original.actor_id, original.created_at) != \
                (row.id, institute, row.operation_id, row.previous_id, row.idempotency_key, row.actor_id, explicit_utc_instant(row.created_at)) or original.created_at > now:
            raise ValueError("Canonical decision columns or clock mismatch")
        return Envelope(original=row.original, fingerprint=row.fingerprint)
    except (ValueError, TypeError, KeyError, OverflowError) as error:
        raise business_error("Retained BASE approval requires verification") from error


def state(db, principal, institute, operation_id, *, _now=None):
    principal = guard(principal, institute)
    operation = operations.require(db, principal, institute, operation_id)
    original, now = operations.Original.model_validate(operation.original), _now or utcnow()
    successors = {}
    for row in db.scalars(select(ApprovalOriginal).where(ApprovalOriginal.institute_id == institute,
            ApprovalOriginal.operation_id == operation_id).execution_options(populate_existing=True)):
        envelope = verify(row, institute, now)
        decision = Original.model_validate(envelope.original)
        if decision.previous_id in successors:
            raise business_error("Approval history branches require verification")
        successors[decision.previous_id] = (decision, envelope)
    previous, previous_at, status, chain = None, original.created_at, "pending", []
    while (previous.original["id"] if previous else None) in successors:
        key = previous.original["id"] if previous else None
        decision, envelope = successors.pop(key)
        valid = status == "pending" and decision.decision in {"approve", "decline"} or status == "approved" and decision.decision == "revoke"
        if not valid or decision.operation_fingerprint != operation.fingerprint or decision.created_at < previous_at or \
                decision.previous_fingerprint != (previous.fingerprint if previous else None):
            raise business_error("Approval causal history requires verification")
        if decision.decision == "approve" and (decision.checked_state_fingerprint != original.expected_state_fingerprint or
                decision.source_checked_at < original.created_at or decision.created_at >= original.valid_until):
            raise business_error("Approval source or original validity requires verification")
        chain.append(envelope); previous, previous_at = envelope, decision.created_at
        status = {"approve": "approved", "decline": "declined", "revoke": "revoked"}[decision.decision]
    if successors:
        raise business_error("Disconnected approval history requires verification")
    return State(operation=operation, captured_at=now, decisions=tuple(chain), status=status, expired=now >= original.valid_until)


def decide(db, principal, institute, candidate):
    try:
        principal = guard(principal, institute)
        request = Request.model_validate(candidate.model_dump() if isinstance(candidate, Request) else candidate)
        lock_institute(db, institute)
        now = utcnow()
        current = state(db, principal, institute, request.operation_id, _now=now)
        old = db.scalar(select(ApprovalOriginal).where(ApprovalOriginal.institute_id == institute,
            ApprovalOriginal.idempotency_key == request.idempotency_key).execution_options(populate_existing=True))
        if old:
            receipt = verify(old, institute, now)
            retained = Original.model_validate(receipt.original)
            if Request(**{k: receipt.original[k] for k in Request.model_fields}) != request or retained.actor_id != principal.actor_id or \
                    not any(receipt == entry for entry in current.decisions):
                raise business_error("Approval recovery key retains original terms, actor and operation chain")
            return receipt
        if db.scalar(select(ExecutionOriginal.id).where(ExecutionOriginal.institute_id == institute,
                ExecutionOriginal.operation_id == request.operation_id)) is not None:
            raise business_error("Performed operation cannot acquire a new decision or be undone by revocation")
        previous = current.decisions[-1] if current.decisions else None
        if request.operation_fingerprint != current.operation.fingerprint or \
                (request.previous_id, request.previous_fingerprint) != ((previous.original["id"], previous.fingerprint) if previous else (None, None)):
            raise business_error("Approval requires the exact reviewed operation and current predecessor")
        if not (current.status == "pending" and request.decision in {"approve", "decline"} or current.status == "approved" and request.decision == "revoke"):
            raise business_error("Approval transition is not permitted")
        checked_at = checked_hash = None
        if request.decision == "approve":
            operation = operations.Original.model_validate(current.operation.original)
            if current.expired:
                raise business_error("Expired operation cannot be approved")
            preview = sensitive.preview(db, principal, institute, operation.selection)
            now = utcnow()
            if preview.state_fingerprint != operation.expected_state_fingerprint or now >= operation.valid_until:
                raise business_error("Changed or expired operation must be prepared again")
            checked_at, checked_hash = preview.captured_at, preview.state_fingerprint
        original = Original(**request.model_dump(), id=new_id("base_approval"), institute_id=institute,
            actor_id=principal.actor_id, created_at=now, source_checked_at=checked_at, checked_state_fingerprint=checked_hash)
        raw = original.model_dump(mode="json")
        row = ApprovalOriginal(id=original.id, institute_id=institute, operation_id=request.operation_id,
            previous_id=request.previous_id, idempotency_key=request.idempotency_key, actor_id=principal.actor_id,
            created_at=now, original=raw, fingerprint=fingerprint(raw))
        db.add(row); db.flush()
        receipt = verify(row, institute, now)
        state(db, principal, institute, request.operation_id, _now=now)
        db.commit()
        return receipt
    except ValueError as error:
        db.rollback()
        raise business_error("BASE approval requires valid explicit terms") from error
    except Exception:
        db.rollback()
        raise


def by_key(db, principal, institute, key):
    guard(principal, institute)
    if not isinstance(key, str) or not key or len(key) > 120 or key != key.strip() or any(ord(c) < 32 for c in key):
        raise business_error("Exact approval recovery key required")
    lock_institute(db, institute)
    row = db.scalar(select(ApprovalOriginal).where(ApprovalOriginal.institute_id == institute,
        ApprovalOriginal.idempotency_key == key).execution_options(populate_existing=True))
    if row is None:
        return None
    receipt = verify(row, institute, utcnow())
    current = state(db, principal, institute, row.operation_id)
    if receipt not in current.decisions:
        raise business_error("Approval recovery requires a verified operation chain")
    return receipt
