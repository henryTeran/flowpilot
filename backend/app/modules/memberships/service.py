from datetime import timedelta, timezone
from hashlib import sha256
import json
from sqlalchemy import select
from app.modules.customers.repository import require_customer
from app.modules.memberships.models import CustomerMembership, MembershipPlan, MembershipRenewal
from app.modules.tickets.repository import lock_institute
from app.shared.exceptions import business_error, not_found
from app.shared.ids import new_id
from app.shared.time import utcnow


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def membership_view(row, now=None):
    now = now or utcnow()
    status = "scheduled" if now < aware(row.active_from) else "active" if now < aware(row.active_until) else "expired"
    return {field: getattr(row, field) for field in (
        "id", "institute_id", "plan_id", "customer_id", "name", "valid_days", "issued_at", "active_from", "active_until"
    )} | {"status": status}


def scoped_membership(db, institute, identifier):
    row = db.scalar(select(CustomerMembership).where(CustomerMembership.id == identifier,
                                                     CustomerMembership.institute_id == institute))
    if row is None:
        raise not_found("Abonnement introuvable")
    db.refresh(row)
    return row


def create_plan(db, institute, payload, actor):
    lock_institute(db, institute)
    fingerprint = sha256(json.dumps(payload.model_dump(exclude={"idempotency_key"}),
                                   sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    existing = db.scalar(select(MembershipPlan).where(MembershipPlan.institute_id == institute,
                                    MembershipPlan.idempotency_key == payload.idempotency_key))
    if existing:
        if existing.creation_fingerprint != fingerprint:
            raise business_error("Cette cle appartient a une autre configuration d'abonnement")
        return existing
    plan = MembershipPlan(id=new_id("mp"), institute_id=institute, actor_id=actor,
                          creation_fingerprint=fingerprint, **payload.model_dump())
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def ensure_no_other_active(db, institute, customer, now, exclude=None):
    other = db.scalar(select(CustomerMembership.id).where(
        CustomerMembership.institute_id == institute, CustomerMembership.customer_id == customer,
        CustomerMembership.active_until > now,
        CustomerMembership.id != exclude if exclude else True,
    ))
    if other:
        raise business_error("Un autre abonnement est deja actif pour cette cliente")


def issue_membership(db, institute, payload, actor):
    lock_institute(db, institute)
    existing = db.scalar(select(CustomerMembership).where(CustomerMembership.institute_id == institute,
                                     CustomerMembership.idempotency_key == payload.idempotency_key))
    if existing:
        if (existing.plan_id, existing.customer_id) != (payload.plan_id, payload.customer_id):
            raise business_error("Cette cle appartient a une autre attribution d'abonnement")
        db.refresh(existing)
        return existing
    require_customer(db, institute, payload.customer_id)
    plan = db.scalar(select(MembershipPlan).where(MembershipPlan.id == payload.plan_id,
                                                MembershipPlan.institute_id == institute))
    if plan is None:
        raise not_found("Formule d'abonnement introuvable")
    now = utcnow()
    ensure_no_other_active(db, institute, payload.customer_id, now)
    row = CustomerMembership(id=new_id("membership"), institute_id=institute, plan_id=plan.id,
        customer_id=payload.customer_id, name=plan.name, valid_days=plan.valid_days,
        issued_at=now, active_from=now, active_until=now + timedelta(days=plan.valid_days),
        idempotency_key=payload.idempotency_key, actor_id=actor)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def renew_membership(db, institute, identifier, payload, actor):
    lock_institute(db, institute)
    existing = db.scalar(select(MembershipRenewal).where(MembershipRenewal.institute_id == institute,
                                     MembershipRenewal.idempotency_key == payload.idempotency_key))
    if existing:
        if existing.membership_id != identifier:
            raise business_error("Cette cle appartient au renouvellement d'un autre abonnement")
        return existing
    row = scoped_membership(db, institute, identifier)
    require_customer(db, institute, row.customer_id)
    now = utcnow()
    ensure_no_other_active(db, institute, row.customer_id, now, row.id)
    previous_from, previous_until = aware(row.active_from), aware(row.active_until)
    active_from = now if now >= previous_until else previous_from
    active_until = max(now, previous_until) + timedelta(days=row.valid_days)
    renewal = MembershipRenewal(id=new_id("mr"), institute_id=institute, membership_id=row.id,
        previous_from=previous_from, previous_until=previous_until, active_from=active_from,
        active_until=active_until, occurred_at=now, idempotency_key=payload.idempotency_key, actor_id=actor)
    row.active_from, row.active_until = active_from, active_until
    db.add(renewal)
    db.commit()
    db.refresh(renewal)
    return renewal
