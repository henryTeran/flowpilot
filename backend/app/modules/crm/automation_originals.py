from typing import Annotated
from pydantic import AwareDatetime, StringConstraints
from sqlalchemy import select
from app.modules.crm.metrics import Fact, Identifier
from app.modules.crm.models import AutomationPolicyOriginal, AutomationPolicyHead
from app.modules.crm.automation_policy import AutomationPolicy
from app.modules.tickets.repository import lock_institute
from app.shared.exceptions import business_error, not_found
from app.shared.ids import new_id
from app.shared.time import explicit_utc_instant, utcnow

Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=240)]
Key = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class PolicyCreate(Fact):
    policy: AutomationPolicy
    previous_policy_id: Identifier | None
    reason: Reason
    idempotency_key: Key


class PolicyRead(PolicyCreate):
    id: Identifier
    institute_id: Identifier
    actor_id: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    created_at: AwareDatetime


def snapshot(row):
    result = PolicyRead(id=row.id, institute_id=row.institute_id, policy=row.policy,
        previous_policy_id=row.previous_policy_id, reason=row.reason, idempotency_key=row.idempotency_key,
        actor_id=row.actor_id, created_at=explicit_utc_instant(row.created_at))
    if result.policy.institute_id != result.institute_id:
        raise business_error("Stored policy scope is incoherent")
    return result


def original(db, institute, key):
    row = db.scalar(select(AutomationPolicyOriginal).where(AutomationPolicyOriginal.institute_id == institute,
        AutomationPolicyOriginal.idempotency_key == key))
    return snapshot(row) if row else None


def require(db, institute, identifier):
    row = db.scalar(select(AutomationPolicyOriginal).where(AutomationPolicyOriginal.institute_id == institute,
        AutomationPolicyOriginal.id == identifier))
    if row is None:
        raise not_found("CRM policy not found")
    return snapshot(row)


def current(db, institute):
    lock_institute(db, institute)
    head = read_head(db, institute)
    return require(db, institute, head.policy_id) if head else None


def read_head(db, institute):
    return db.scalar(select(AutomationPolicyHead).where(AutomationPolicyHead.institute_id == institute)
        .execution_options(populate_existing=True))


def create(db, institute, payload, actor):
    if not isinstance(actor, str) or not actor.strip() or len(actor) > 160:
        raise business_error("A signed policy actor is required")
    lock_institute(db, institute)
    old = original(db, institute, payload.idempotency_key)
    if old:
        if old.actor_id != actor or old.model_dump(include=set(PolicyCreate.model_fields)) != payload.model_dump():
            raise business_error("The key retains the original policy terms and actor")
        return old
    if payload.policy.institute_id != institute:
        raise business_error("The policy institute must match the requested owner")
    head = read_head(db, institute)
    if payload.previous_policy_id != (head.policy_id if head else None):
        raise business_error("The current policy changed; reread before declaring a correction")
    now = utcnow()
    if head and now < require(db, institute, head.policy_id).created_at:
        raise business_error("The policy clock precedes its original predecessor")
    row = AutomationPolicyOriginal(id=new_id("crm_automation_policy"), institute_id=institute,
        policy=payload.policy.model_dump(mode="json"), previous_policy_id=payload.previous_policy_id,
        reason=payload.reason, idempotency_key=payload.idempotency_key, actor_id=actor, created_at=now)
    db.add(row)
    db.flush()
    if head:
        head.policy_id = row.id
    else:
        db.add(AutomationPolicyHead(institute_id=institute, policy_id=row.id))
    db.commit()
    db.refresh(row)
    return snapshot(row)
