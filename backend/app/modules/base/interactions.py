"""Scoped append-only attempt/result journal; no public write or raw text retention."""
from typing import Literal
from datetime import timezone
from pydantic import AwareDatetime, model_validator
from sqlalchemy import select
from app.modules.base import read_capabilities as base, plans
from app.modules.base.models import InteractionOriginal
from app.modules.crm.metrics import Fact, Count
from app.modules.waitlist.originals import Envelope, fingerprint
from app.modules.tickets.repository import lock_institute
from app.shared.time import utcnow, explicit_utc_instant
from app.shared.ids import new_id
from app.shared.exceptions import business_error

Action = Literal["capabilities", "sensitive_capabilities", "execution_capabilities", "resolve_context", "resolve_intent",
    "read", "prepare_plan", "plan_by_key", "plan_detail", "plan_history", "preview_cancellation", "prepare_operation",
    "operation_by_key", "operation_detail", "operation_history", "decide", "decision_by_key", "approval_state",
    "execute", "execution_by_key", "execution_for_operation"]

class Original(Fact):
    id: base.ExactId
    institute_id: base.ExactId
    sequence: Count
    principal: base.Principal
    created_at: AwareDatetime
    previous_id: base.ExactId | None
    previous_fingerprint: base.Digest | None
    action: Action
    request_fingerprint: base.Digest
    kind: Literal["attempt", "succeeded", "refused", "failed"]
    attempt_id: base.ExactId | None
    attempt_fingerprint: base.Digest | None
    status_code: Count | None
    response_fingerprint: base.Digest | None
    retention: Literal["digests_only_no_raw_request_response_or_error_text"] = "digests_only_no_raw_request_response_or_error_text"

    @model_validator(mode="after")
    def shape(self):
        if self.sequence < 1 or self.principal.institute_id != self.institute_id or self.principal.role not in ("responsable_institut", "accueil"):
            raise ValueError("Exact signed journal scope required")
        if self.created_at.utcoffset().total_seconds() != 0:
            raise ValueError("Canonical UTC clock required")
        if (self.previous_id is None) != (self.previous_fingerprint is None) or (self.sequence == 1) != (self.previous_id is None):
            raise ValueError("Exact preceding journal proof required")
        if self.kind == "attempt":
            if any(v is not None for v in (self.attempt_id, self.attempt_fingerprint, self.status_code, self.response_fingerprint)):
                raise ValueError("Attempt cannot assert an outcome")
        elif self.attempt_id is None or self.attempt_fingerprint is None:
            raise ValueError("Exact attempt proof required")
        elif self.kind == "succeeded":
            if self.status_code != 200 or self.response_fingerprint is None:
                raise ValueError("Success requires a full response digest")
        elif self.kind == "refused":
            if self.status_code not in (400, 403, 404, 409, 422) or self.response_fingerprint is not None:
                raise ValueError("Refusal excludes private error text")
        elif self.status_code not in (500, 502, 503) or self.response_fingerprint is not None:
            raise ValueError("Failure excludes private error text")
        return self

class Audit(Fact):
    institute_id: base.ExactId
    captured_at: AwareDatetime
    offset: Count
    limit: Count
    total: Count
    originals: tuple[Envelope, ...]
    unresolved_attempts: Count
    integrity: Literal["verified_retained_chain_not_signature_or_external_truncation_anchor"] = "verified_retained_chain_not_signature_or_external_truncation_anchor"

def guard(principal, institute):
    try:
        user = base.Principal.model_validate(principal.model_dump())
    except (ValueError, AttributeError) as error:
        raise business_error("Exact journal principal required") from error
    if user.institute_id != institute or user.role not in ("responsable_institut", "accueil"):
        from fastapi import HTTPException
        raise HTTPException(403, "Journal scope refused")
    return user

def _cohort(db, institute):
    retained, attempts, completed, previous = [], {}, set(), None
    captured = utcnow()
    for row in db.scalars(select(InteractionOriginal).where(InteractionOriginal.institute_id == institute)
            .order_by(InteractionOriginal.sequence).execution_options(populate_existing=True)):
        try:
            value = Original.model_validate(row.original)
            raw = value.model_dump(mode="json")
            if value.created_at > captured:
                raise ValueError("Future journal clock")
            if raw != row.original or fingerprint(raw) != row.fingerprint or value.id != row.id or value.institute_id != institute:
                raise ValueError("Raw original proof differs")
            if (value.sequence, value.previous_id, value.attempt_id, value.principal.actor_id, value.created_at) != (
                    row.sequence, row.previous_id, row.attempt_id, row.actor_id, explicit_utc_instant(row.created_at).astimezone(timezone.utc)):
                raise ValueError("Columns differ from original")
            if value.sequence != len(retained)+1 or value.previous_id != (previous.original["id"] if previous else None) or value.previous_fingerprint != (previous.fingerprint if previous else None):
                raise ValueError("Broken journal chain")
            if previous and value.created_at < Original.model_validate(previous.original).created_at:
                raise ValueError("Journal chronology differs")
            envelope = Envelope(original=raw, fingerprint=row.fingerprint)
            if value.kind == "attempt":
                attempts[value.id] = envelope
            else:
                attempt = attempts.get(value.attempt_id)
                if attempt is None or value.attempt_id in completed or value.attempt_fingerprint != attempt.fingerprint:
                    raise ValueError("Missing or completed attempt")
                original = Original.model_validate(attempt.original)
                if (value.principal, value.action, value.request_fingerprint) != (original.principal, original.action, original.request_fingerprint):
                    raise ValueError("Outcome belongs to another interaction")
                completed.add(value.attempt_id)
            retained.append(envelope); previous = envelope
        except (ValueError, TypeError, KeyError) as error:
            raise business_error("Retained BASE interaction chain requires verification") from error
    return retained, attempts, completed

def _append(db, user, institute, values):
    lock_institute(db, institute)
    retained, attempts, completed = _cohort(db, institute)
    if values["kind"] != "attempt":
        attempt = attempts.get(values["attempt_id"])
        if attempt is None or values["attempt_id"] in completed or attempt.fingerprint != values["attempt_fingerprint"]:
            raise business_error("Exact pending interaction required")
        parent = Original.model_validate(attempt.original)
        if (user, values["action"], values["request_fingerprint"]) != (parent.principal, parent.action, parent.request_fingerprint):
            raise business_error("Interaction actor or request differs")
    previous = retained[-1] if retained else None
    value = Original(id=new_id("base_interaction"), institute_id=institute, principal=user, sequence=len(retained)+1,
        created_at=utcnow(), previous_id=previous.original["id"] if previous else None,
        previous_fingerprint=previous.fingerprint if previous else None, **values)
    raw = value.model_dump(mode="json")
    row = InteractionOriginal(id=value.id, institute_id=institute, sequence=value.sequence, previous_id=value.previous_id,
        attempt_id=value.attempt_id, actor_id=user.actor_id, created_at=value.created_at, original=raw, fingerprint=fingerprint(raw))
    db.add(row); db.flush()
    verified, _, _ = _cohort(db, institute)
    db.commit()
    return verified[-1]

def begin(db, principal, institute, action: Action, request):
    try:
        user = guard(principal, institute)
        return _append(db, user, institute, dict(action=action, request_fingerprint=fingerprint(request), kind="attempt",
            attempt_id=None, attempt_fingerprint=None, status_code=None, response_fingerprint=None))
    except Exception:
        db.rollback(); raise

def finish(db, principal, institute, attempt: Envelope, status_code: int, response=None):
    try:
        user = guard(principal, institute)
        value = Original.model_validate(attempt.original)
        if value.model_dump(mode="json") != attempt.original or fingerprint(attempt.original) != attempt.fingerprint or value.kind != "attempt":
            raise business_error("Full original attempt proof required")
        if type(status_code) is not int:
            raise business_error("Exact interaction outcome required")
        kind = "succeeded" if status_code == 200 else "refused" if status_code in (400, 403, 404, 409, 422) else "failed"
        return _append(db, user, institute, dict(action=value.action, request_fingerprint=value.request_fingerprint,
            kind=kind, attempt_id=value.id, attempt_fingerprint=attempt.fingerprint, status_code=status_code,
            response_fingerprint=fingerprint(response) if kind == "succeeded" else None))
    except Exception:
        db.rollback(); raise

def audit(db, principal, institute, offset=0, limit=20):
    plans.guard(principal, institute)
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 50:
        raise business_error("Exact journal bounds required")
    lock_institute(db, institute)
    retained, attempts, completed = _cohort(db, institute)
    return Audit(institute_id=institute, captured_at=utcnow(), offset=offset, limit=limit, total=len(retained),
        originals=tuple(retained[offset:offset+limit]), unresolved_attempts=len(attempts)-len(completed))
