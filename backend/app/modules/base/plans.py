"""Retained explicit read/suggest preparation, not sensitive execution approval."""
from typing import Annotated, Literal
from pydantic import AwareDatetime, StringConstraints, model_validator
from sqlalchemy import select
from app.modules.base import intents, read_capabilities as base
from app.modules.base.models import PlanOriginal
from app.modules.crm.metrics import Fact, Count
from app.modules.waitlist.originals import Envelope, fingerprint
from app.modules.tickets.repository import lock_institute
from app.shared.time import utcnow, explicit_utc_instant
from app.shared.ids import new_id
from app.shared.exceptions import business_error, not_found

Key = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=120)]
Reason = Annotated[str, StringConstraints(strict=True, min_length=3, max_length=240)]


class Request(Fact):
    intent: intents.Request
    reason: Reason
    idempotency_key: Key

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
    resolution: intents.Resolution
    evidence: base.Evidence
    effect: Literal["retained_read_suggest_preparation_not_approval_or_execution"] = "retained_read_suggest_preparation_not_approval_or_execution"

    @model_validator(mode="after")
    def causal_preparation(self):
        principal = self.resolution.principal
        if (principal.actor_id, principal.institute_id) != (self.actor_id, self.institute_id):
            raise ValueError("Plan actor and institute must match signed intent")
        resolved = self.resolution
        selected = [s for s in self.intent.selections if resolved.invocation is not None and s.capability == resolved.invocation.capability]
        if resolved.status != "ready" or resolved.reason != "explicit_selection_ready" or resolved.proposal.status != "recognized" or \
                resolved.invocation is None or resolved.proposal.capabilities != (resolved.invocation.capability,) or \
                len(selected) != 1 or selected[0] != resolved.invocation or \
                resolved.request_fingerprint != fingerprint(self.intent.model_dump(mode="json")) or \
                base.resolve(principal, self.institute_id, resolved.invocation)[0] != resolved.context or resolved.context != self.evidence.context:
            raise ValueError("Plan must retain the exact resolved selection and delegated evidence")
        if self.evidence.read_completed_at > self.created_at:
            raise ValueError("Preparation cannot precede its delegated read completion")
        invocation, result = resolved.invocation, self.evidence.result
        if isinstance(invocation, base.ReadInvocation):
            if not isinstance(result, base.lifecycle.State):
                raise ValueError("Read preparation requires a lifecycle result")
            state = result
        else:
            if isinstance(invocation, base.MatchInvocation):
                if not isinstance(result, base.matching.Read):
                    raise ValueError("Matching preparation requires a matching result")
                source, policy = result, invocation.arguments.policy
            else:
                if not isinstance(result, base.optimizer.Read) or result.institute_id != self.institute_id or \
                        result.policy_original.original.get("id") != invocation.arguments.policy_id or \
                        result.policy_original.fingerprint != invocation.arguments.policy_fingerprint:
                    raise ValueError("Scoring preparation requires its selected policy result")
                source, policy = result.source, invocation.arguments.matching_policy
            if source.policy != policy or source.horizon_end != invocation.arguments.horizon_end or source.captured_at > self.evidence.read_completed_at:
                raise ValueError("Current source must retain the selected rules, horizon and capture")
            state = source.state
            if not state.events or state.events[-1].original.get("id") != invocation.arguments.expected_event_id or \
                    state.events[-1].fingerprint != invocation.arguments.expected_event_fingerprint:
                raise ValueError("Current source must retain the selected causal head")
        if state.root.original.get("id") != invocation.arguments.root_id or state.root.original.get("institute_id") != self.institute_id:
            raise ValueError("Preparation evidence requires the selected owned root")
        snapshots = (state.root, state.current_demand, *state.events)
        if isinstance(result, base.optimizer.Read):
            snapshots += (result.policy_original,)
        if any(fingerprint(s.original) != s.fingerprint for s in snapshots):
            raise ValueError("Nested retained references must preserve their complete raw SHA")
        if self.id != self.id.strip() or any(ord(c) < 32 for c in self.id):
            raise ValueError("An exact plan ID is required")
        return self


class Audit(Fact):
    institute_id: base.ExactId
    captured_at: AwareDatetime
    offset: Count
    limit: Count
    total: Count
    originals: tuple[Envelope, ...]
    basis: Literal["verified_retained_preparations_not_complete_interaction_or_execution_audit"] = "verified_retained_preparations_not_complete_interaction_or_execution_audit"


def guard(principal, institute):
    return base.authorize(principal, institute, "WAITLIST_READ")[0]


def verify(row, institute, now):
    try:
        if row.institute_id != institute or fingerprint(row.original) != row.fingerprint:
            raise ValueError("Plan ownership or raw SHA mismatch")
        original = Original.model_validate(row.original)
        if original.model_dump(mode="json") != row.original:
            raise ValueError("Canonical complete plan snapshot required")
        if (original.id, original.institute_id, original.actor_id, original.idempotency_key, original.created_at) != \
                (row.id, institute, row.actor_id, row.idempotency_key, explicit_utc_instant(row.created_at)) or original.created_at > now:
            raise ValueError("Plan columns or clock mismatch")
        return Envelope(original=row.original, fingerprint=row.fingerprint)
    except (ValueError, TypeError, KeyError, OverflowError) as error:
        raise business_error("Retained BASE preparation requires verification") from error


def _row(db, institute, field, value):
    return db.scalar(select(PlanOriginal).where(PlanOriginal.institute_id == institute, field == value).execution_options(populate_existing=True))


def create(db, principal, institute, candidate):
    try:
        principal = guard(principal, institute)
        request = Request.model_validate(candidate.model_dump() if isinstance(candidate, Request) else candidate)
        lock_institute(db, institute)
        old = _row(db, institute, PlanOriginal.idempotency_key, request.idempotency_key)
        if old:
            receipt = verify(old, institute, utcnow())
            original = Original.model_validate(receipt.original)
            terms = Request(intent=original.intent, reason=original.reason, idempotency_key=original.idempotency_key)
            if terms != request or original.actor_id != principal.actor_id:
                raise business_error("BASE recovery key retains the exact original request and actor")
            return receipt
        resolution = intents.resolve(principal, institute, request.intent, interpreter=intents.UpstreamInterpreter())
        if resolution.status != "ready":
            raise business_error("Clarify intent and select exactly one reference before preparing")
        # Explicit preparation captures existing service facts/refusals, never a new allocator.
        evidence = base.invoke(db, principal, institute, resolution.invocation)
        now = utcnow()
        original = Original(**request.model_dump(), id=new_id("base_plan"), institute_id=institute,
            actor_id=principal.actor_id, created_at=now, resolution=resolution, evidence=evidence)
        raw = original.model_dump(mode="json")
        row = PlanOriginal(id=original.id, institute_id=institute, actor_id=principal.actor_id,
            idempotency_key=original.idempotency_key, created_at=now, original=raw, fingerprint=fingerprint(raw))
        db.add(row); db.flush()
        receipt = verify(row, institute, now)
        db.commit()
        return receipt
    except ValueError as error:
        db.rollback()
        raise business_error("BASE preparation requires valid explicit terms") from error
    except Exception:
        db.rollback()
        raise


def by_key(db, principal, institute, key):
    guard(principal, institute)
    if not isinstance(key, str) or not key or len(key) > 120 or key != key.strip() or any(ord(c) < 32 for c in key):
        raise business_error("Exact BASE recovery key required")
    lock_institute(db, institute)
    row = _row(db, institute, PlanOriginal.idempotency_key, key)
    return verify(row, institute, utcnow()) if row else None


def require(db, principal, institute, identifier):
    guard(principal, institute)
    lock_institute(db, institute)
    row = _row(db, institute, PlanOriginal.id, identifier)
    if row is None:
        raise not_found("Retained BASE preparation not found")
    return verify(row, institute, utcnow())


def audit(db, principal, institute, offset=0, limit=20):
    guard(principal, institute)
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 50:
        raise business_error("Invalid BASE history bounds")
    lock_institute(db, institute)
    now, total, rows = utcnow(), 0, []
    for row in db.scalars(select(PlanOriginal).where(PlanOriginal.institute_id == institute)
            .order_by(PlanOriginal.created_at, PlanOriginal.id).execution_options(yield_per=100, populate_existing=True)):
        receipt = verify(row, institute, now)
        if offset <= total < offset+limit:
            rows.append(receipt)
        total += 1
    return Audit(institute_id=institute, captured_at=now, offset=offset, limit=limit, total=total, originals=tuple(rows))
