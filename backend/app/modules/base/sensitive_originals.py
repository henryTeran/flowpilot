"""Version-pinned pending operations; preparation never implies human approval."""
from typing import Literal
from datetime import timezone, timedelta
from pydantic import AwareDatetime, model_validator, field_validator
from sqlalchemy import select
from app.modules.base import read_capabilities as base, sensitive_capabilities as sensitive
from app.modules.base.plans import Key, Reason, guard
from app.modules.base.models import SensitiveOperationOriginal
from app.modules.crm.metrics import Fact, Count
from app.modules.waitlist.originals import Envelope, fingerprint
from app.modules.tickets.repository import lock_institute
from app.shared.time import utcnow, explicit_utc_instant
from app.shared.ids import new_id
from app.shared.exceptions import business_error, not_found


class Request(Fact):
    capability: Literal["APPOINTMENT_CANCEL"]
    selection: sensitive.Selection
    expected_state_fingerprint: base.Digest
    valid_until: base.matching.Horizon
    reason: Reason
    idempotency_key: Key

    @field_validator("valid_until")
    @classmethod
    def canonical_validity(cls, value):
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def exact_terms(self):
        if any(v != v.strip() or any(ord(c) < 32 for c in v) for v in (self.reason, self.idempotency_key)):
            raise ValueError("Exact preparation reason and recovery key required")
        return self


class Original(Request):
    id: base.ExactId
    institute_id: base.ExactId
    actor_id: base.Actor
    created_at: AwareDatetime
    preview: sensitive.Preview
    effect: Literal["prepared_sensitive_operation_only_pending_human_approval_no_execution"] = "prepared_sensitive_operation_only_pending_human_approval_no_execution"

    @model_validator(mode="after")
    def binding(self):
        if (self.preview.principal.actor_id, self.preview.principal.institute_id, self.preview.appointment_id, self.preview.state_fingerprint) != \
                (self.actor_id, self.institute_id, self.selection.appointment_id, self.expected_state_fingerprint) or \
                self.created_at.utcoffset() != timedelta(0) or not self.preview.captured_at <= self.created_at < self.valid_until or self.capability != self.preview.capability.name:
            raise ValueError("Sensitive preparation requires its exact signed current selection and explicit validity")
        if self.id != self.id.strip() or any(ord(c) < 32 for c in self.id):
            raise ValueError("An exact operation ID is required")
        return self


class Audit(Fact):
    institute_id: base.ExactId
    captured_at: AwareDatetime
    offset: Count
    limit: Count
    total: Count
    originals: tuple[Envelope, ...]
    basis: Literal["verified_pending_sensitive_preparations_not_approval_execution_or_current_eligibility"] = "verified_pending_sensitive_preparations_not_approval_execution_or_current_eligibility"


def verify(row, institute, now):
    try:
        if row.institute_id != institute or fingerprint(row.original) != row.fingerprint:
            raise ValueError("Operation ownership/raw SHA mismatch")
        original = Original.model_validate(row.original)
        if original.model_dump(mode="json") != row.original or \
                (original.id, original.institute_id, original.actor_id, original.idempotency_key, original.created_at) != \
                (row.id, institute, row.actor_id, row.idempotency_key, explicit_utc_instant(row.created_at)) or original.created_at > now:
            raise ValueError("Canonical operation columns or clock mismatch")
        return Envelope(original=row.original, fingerprint=row.fingerprint)
    except (ValueError, TypeError, KeyError, OverflowError) as error:
        raise business_error("Retained sensitive BASE operation requires verification") from error


def _row(db, institute, field, value):
    return db.scalar(select(SensitiveOperationOriginal).where(SensitiveOperationOriginal.institute_id == institute,
        field == value).execution_options(populate_existing=True))


def create(db, principal, institute, candidate):
    try:
        principal = guard(principal, institute)
        request = Request.model_validate(candidate.model_dump() if isinstance(candidate, Request) else candidate)
        lock_institute(db, institute)
        old = _row(db, institute, SensitiveOperationOriginal.idempotency_key, request.idempotency_key)
        if old:
            receipt = verify(old, institute, utcnow())
            original = Original.model_validate(receipt.original)
            if Request(**{k: receipt.original[k] for k in Request.model_fields}) != request or original.actor_id != principal.actor_id:
                raise business_error("Sensitive recovery key retains the original request and actor")
            return receipt
        preview = sensitive.preview(db, principal, institute, request.selection)
        now = utcnow()
        if preview.state_fingerprint != request.expected_state_fingerprint or request.valid_until <= now:
            raise business_error("Sensitive preparation requires fresh reviewed state and future explicit validity")
        original = Original(**request.model_dump(), id=new_id("base_operation"), institute_id=institute,
            actor_id=principal.actor_id, created_at=now, preview=preview)
        raw = original.model_dump(mode="json")
        row = SensitiveOperationOriginal(id=original.id, institute_id=institute, actor_id=principal.actor_id,
            idempotency_key=original.idempotency_key, created_at=now, original=raw, fingerprint=fingerprint(raw))
        db.add(row); db.flush()
        receipt = verify(row, institute, now)
        db.commit()
        return receipt
    except ValueError as error:
        db.rollback()
        raise business_error("Sensitive BASE preparation requires valid explicit terms") from error
    except Exception:
        db.rollback()
        raise


def by_key(db, principal, institute, key):
    guard(principal, institute)
    if not isinstance(key, str) or not key or len(key) > 120 or key != key.strip() or any(ord(c) < 32 for c in key):
        raise business_error("Exact sensitive recovery key required")
    lock_institute(db, institute)
    row = _row(db, institute, SensitiveOperationOriginal.idempotency_key, key)
    return verify(row, institute, utcnow()) if row else None


def require(db, principal, institute, identifier):
    guard(principal, institute)
    lock_institute(db, institute)
    row = _row(db, institute, SensitiveOperationOriginal.id, identifier)
    if row is None:
        raise not_found("Retained sensitive operation not found")
    return verify(row, institute, utcnow())


def audit(db, principal, institute, offset=0, limit=20):
    guard(principal, institute)
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 50:
        raise business_error("Invalid sensitive history bounds")
    lock_institute(db, institute)
    now, total, rows = utcnow(), 0, []
    for row in db.scalars(select(SensitiveOperationOriginal).where(SensitiveOperationOriginal.institute_id == institute)
            .order_by(SensitiveOperationOriginal.created_at, SensitiveOperationOriginal.id).execution_options(yield_per=100, populate_existing=True)):
        receipt = verify(row, institute, now)
        if offset <= total < offset+limit:
            rows.append(receipt)
        total += 1
    return Audit(institute_id=institute, captured_at=now, offset=offset, limit=limit, total=total, originals=tuple(rows))
