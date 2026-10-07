"""Immutable conditional calculations: key recovery, full originals and audit reads."""
from hashlib import sha256
import json
from typing import Annotated, Literal
from pydantic import AwareDatetime, StringConstraints, field_validator
from sqlalchemy import select
from app.modules.crm.metrics import Fact, Identifier, Count
from app.modules.crm.policies import Reason, Key
from app.modules.revenue import scenarios
from app.modules.revenue.models import ScenarioOriginal
from app.modules.tickets.repository import lock_institute
from app.shared.exceptions import business_error, not_found
from app.shared.ids import new_id
from app.shared.time import explicit_utc_instant, utcnow


class Declaration(Fact):
    assumptions: scenarios.Request
    reason: Reason
    idempotency_key: Key


class Original(scenarios.Calculation):
    id: Identifier
    reason: Reason
    idempotency_key: Key
    created_at: AwareDatetime
    retained: Literal[True] = True

    @field_validator("retained", mode="before")
    @classmethod
    def explicit_retention(cls, value):
        if value is not True:
            raise ValueError("Only an explicit retained original is supported")
        return value


class Envelope(Fact):
    original: dict
    fingerprint: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class Audit(Fact):
    institute_id: Identifier
    captured_at: AwareDatetime
    offset: Count
    limit: Count
    total: Count
    originals: tuple[Envelope, ...]
    full_original_cohort_verified: Literal[True] = True
    complete_sales_history: Literal[False] = False
    action_executed: Literal[False] = False

    @field_validator("full_original_cohort_verified", "complete_sales_history", "action_executed", mode="before")
    @classmethod
    def strict_claim(cls, value, info):
        if value is not (True if info.field_name == "full_original_cohort_verified" else False):
            raise ValueError("Audit claims must be explicit")
        return value


def fingerprint(original):
    return sha256(json.dumps(original, sort_keys=True, ensure_ascii=True,
        separators=(",", ":"), allow_nan=False).encode("ascii")).hexdigest()


def verify(row, institute, now):
    try:
        if row.institute_id != institute or fingerprint(row.original) != row.fingerprint:
            raise ValueError("Original fingerprint or institute mismatch")
        original = Original.model_validate(row.original)
        if (original.id, original.institute_id, original.actor_id, original.idempotency_key, original.created_at) != \
            (row.id, institute, row.actor_id, row.idempotency_key, explicit_utc_instant(row.created_at)) \
            or original.created_at != original.evidence.window.captured_at or original.created_at > now:
            raise ValueError("Original identity, actor, key and capture must bind stored columns")
        if original.id != original.id.strip() or original.reason != row.original["reason"] \
            or original.idempotency_key != row.original["idempotency_key"]:
            raise ValueError("Original identifiers and declarations must remain exact")
        result = scenarios.calculate(institute, original.actor_id, original.assumptions, original.evidence)
        expected = result.model_dump(mode="json", exclude={"retained"})
        actual = original.model_dump(mode="json", include=set(scenarios.Calculation.model_fields))
        if actual != expected:
            raise ValueError("Stored scenario calculation no longer agrees with its own source")
        # Return the full original JSON, not a normalized datetime projection.
        return Envelope(original=row.original, fingerprint=row.fingerprint)
    except (ValueError, TypeError, KeyError, OverflowError) as error:
        raise business_error("Retained scenario original requires verification") from error


def _row(db, institute, field, value):
    return db.scalar(select(ScenarioOriginal).where(ScenarioOriginal.institute_id == institute,
        field == value).execution_options(populate_existing=True))


def by_key(db, institute, key):
    if not isinstance(key, str) or not key or key != key.strip() or len(key) > 120:
        raise business_error("An exact scenario recovery key is required")
    lock_institute(db, institute)
    row = _row(db, institute, ScenarioOriginal.idempotency_key, key)
    return verify(row, institute, utcnow()) if row else None


def require(db, institute, identifier):
    lock_institute(db, institute)
    row = _row(db, institute, ScenarioOriginal.id, identifier)
    if row is None:
        raise not_found("Retained scenario original not found")
    return verify(row, institute, utcnow())


def create(db, institute, payload: Declaration, actor):
    try:
        payload = Declaration.model_validate(payload.model_dump())
        if not isinstance(actor, str) or not actor or actor != actor.strip() or len(actor) > 160 or any(ord(c) < 32 for c in actor):
            raise ValueError("An explicit signed scenario actor is required")
        lock_institute(db, institute)
        row = _row(db, institute, ScenarioOriginal.idempotency_key, payload.idempotency_key)
        if row:
            retained = verify(row, institute, utcnow())
            old = Original.model_validate(retained.original)
            if old.actor_id != actor or Declaration(assumptions=old.assumptions, reason=old.reason,
                idempotency_key=old.idempotency_key) != payload:
                raise business_error("The scenario key retains its original assumptions, reason and actor")
            return retained
        calculation = scenarios.preview(db, institute, payload.assumptions, actor)
        captured = calculation.evidence.window.captured_at
        original = Original(**calculation.model_dump(exclude={"retained"}), id=new_id("revenue_scenario"),
            reason=payload.reason, idempotency_key=payload.idempotency_key, created_at=captured)
        raw = original.model_dump(mode="json")
        row = ScenarioOriginal(id=original.id, institute_id=institute, idempotency_key=payload.idempotency_key,
            actor_id=actor, created_at=captured, original=raw, fingerprint=fingerprint(raw))
        db.add(row); db.flush()
        result = verify(row, institute, captured)
        db.commit()
        return result
    except ValueError as error:
        db.rollback()
        raise business_error("Scenario declaration or sources require verification") from error
    except Exception:
        db.rollback()
        raise


def audit(db, institute, offset=0, limit=20):
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 50:
        raise business_error("Invalid scenario audit page bounds")
    lock_institute(db, institute)
    now = utcnow()
    originals, total = [], 0
    # A bounded output page never bounds the original verification cohort.
    for row in db.scalars(select(ScenarioOriginal).where(ScenarioOriginal.institute_id == institute)
        .order_by(ScenarioOriginal.created_at, ScenarioOriginal.id).execution_options(yield_per=100, populate_existing=True)):
        original = verify(row, institute, now)
        if offset <= total < offset + limit:
            originals.append(original)
        total += 1
    return Audit(institute_id=institute, captured_at=now, offset=offset, limit=limit,
        total=total, originals=tuple(originals))
