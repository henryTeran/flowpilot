"""Retained explicit scoring assumptions, not a mutable default or booking policy."""
from typing import Annotated, Literal
from pydantic import AwareDatetime, StringConstraints, model_validator
from sqlalchemy import select
from app.modules.optimizer import policy
from app.modules.optimizer.models import PolicyOriginal
from app.modules.waitlist.originals import Envelope, fingerprint
from app.modules.waitlist.domain import Fact
from app.modules.crm.metrics import Identifier, Count
from app.modules.crm.policies import Reason, Key
from app.modules.tickets.repository import lock_institute
from app.shared.time import utcnow, explicit_utc_instant
from app.shared.ids import new_id
from app.shared.exceptions import business_error, not_found


class Request(Fact):
    terms: policy.Terms
    reason: Reason
    idempotency_key: Key


class Original(Request):
    id: Identifier
    institute_id: Identifier
    actor_id: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    created_at: AwareDatetime
    action: Literal["scoring_assumptions_only_no_booking_or_contact"] = "scoring_assumptions_only_no_booking_or_contact"

    @model_validator(mode="after")
    def coherent(self):
        policy.scoring_policy(self.terms, self.institute_id, self.id, self.created_at, self.reason)
        if any(v != v.strip() or any(ord(c) < 32 for c in v) for v in (self.id, self.institute_id, self.actor_id, self.idempotency_key)):
            raise ValueError("Original scope/identity/actor/key must remain exact")
        return self


class Audit(Fact):
    institute_id: Identifier
    captured_at: AwareDatetime
    offset: Count
    limit: Count
    total: Count
    originals: tuple[Envelope, ...]
    basis: Literal["verified_retained_scoring_assumptions_not_an_active_default"] = "verified_retained_scoring_assumptions_not_an_active_default"


def verify(row, institute, now):
    try:
        if row.institute_id != institute or fingerprint(row.original) != row.fingerprint:
            raise ValueError("Original ownership/raw fingerprint mismatch")
        original = Original.model_validate(row.original)
        if original.model_dump(mode="json") != row.original:
            raise ValueError("Retained policy must preserve the canonical typed snapshot")
        if (original.id, original.institute_id, original.idempotency_key, original.actor_id, original.created_at) != \
                (row.id, institute, row.idempotency_key, row.actor_id, explicit_utc_instant(row.created_at)) or original.created_at > now:
            raise ValueError("Original columns/capture mismatch")
        return Envelope(original=row.original, fingerprint=row.fingerprint)
    except (ValueError, TypeError, KeyError, OverflowError) as error:
        raise business_error("Retained optimizer policy requires verification") from error


def _row(db, institute, field, value):
    return db.scalar(select(PolicyOriginal).where(PolicyOriginal.institute_id == institute, field == value)
        .execution_options(populate_existing=True))


def by_key(db, institute, key):
    if not isinstance(key, str) or not key or key != key.strip() or len(key) > 120 or any(ord(c) < 32 for c in key):
        raise business_error("An exact recovery key is required")
    lock_institute(db, institute)
    row = _row(db, institute, PolicyOriginal.idempotency_key, key)
    return verify(row, institute, utcnow()) if row else None


def require(db, institute, identifier):
    lock_institute(db, institute)
    row = _row(db, institute, PolicyOriginal.id, identifier)
    if row is None:
        raise not_found("Retained optimizer policy not found")
    return verify(row, institute, utcnow())


def create(db, institute, request: Request, actor):
    try:
        request = Request.model_validate(request.model_dump())
        if not isinstance(actor, str) or not actor or actor != actor.strip() or len(actor) > 160 or any(ord(c) < 32 for c in actor):
            raise ValueError("An explicit signed actor is required")
        lock_institute(db, institute)
        now = utcnow()
        row = _row(db, institute, PolicyOriginal.idempotency_key, request.idempotency_key)
        if row:
            envelope = verify(row, institute, now)
            old = Original.model_validate(envelope.original)
            if Request(terms=old.terms, reason=old.reason, idempotency_key=old.idempotency_key) != request or old.actor_id != actor:
                raise business_error("Recovery key retains the original assumptions and actor")
            return envelope
        original = Original(**request.model_dump(), id=new_id("optimizer_policy"), institute_id=institute, actor_id=actor, created_at=now)
        raw = original.model_dump(mode="json")
        row = PolicyOriginal(id=original.id, institute_id=institute, actor_id=actor, created_at=now,
            idempotency_key=original.idempotency_key, original=raw, fingerprint=fingerprint(raw))
        db.add(row); db.flush()
        result = verify(row, institute, now)
        db.commit()
        return result
    except ValueError as error:
        db.rollback()
        raise business_error("Optimizer policy assumptions require verification") from error
    except Exception:
        db.rollback()
        raise


def audit(db, institute, offset=0, limit=20):
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 50:
        raise business_error("Invalid optimizer policy audit bounds")
    lock_institute(db, institute)
    now, total, rows = utcnow(), 0, []
    for row in db.scalars(select(PolicyOriginal).where(PolicyOriginal.institute_id == institute)
            .order_by(PolicyOriginal.created_at, PolicyOriginal.id).execution_options(yield_per=100, populate_existing=True)):
        result = verify(row, institute, now)
        if offset <= total < offset+limit:
            rows.append(result)
        total += 1
    return Audit(institute_id=institute, captured_at=now, offset=offset, limit=limit, total=total, originals=tuple(rows))
