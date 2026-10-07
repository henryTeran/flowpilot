"""Registered-customer immutable assumptions and locked remaining-value reads."""
from typing import Annotated, Literal
from pydantic import AwareDatetime, ValidationError, StringConstraints
from sqlalchemy import case, func, select
from app.modules.crm import billing
from app.modules.crm.lifetime import LifetimeAssumptions, RemainingLifetimeScenario, calculate_remaining_lifetime
from app.modules.crm.metrics import BillingWindow, Fact, Identifier
from app.modules.crm.models import LifetimeHead, LifetimeOriginal
from app.modules.crm.policies import Reason, Key
from app.modules.crm.segments import RegisteredCustomerFact
from app.modules.customers.repository import require_customer
from app.modules.tickets.models import QueueTicket
from app.modules.tickets.repository import lock_institute
from app.shared.exceptions import business_error, not_found
from app.shared.ids import new_id
from app.shared.time import explicit_utc_instant, utcnow

class Declaration(Fact):
    assumptions: LifetimeAssumptions
    previous_id: Identifier | None
    reason: Reason
    idempotency_key: Key

class Original(Declaration):
    id: Identifier
    institute_id: Identifier
    customer_id: Identifier
    actor_id: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    created_at: AwareDatetime

def snapshot(row):
    result = Original(id=row.id, institute_id=row.institute_id, customer_id=row.customer_id,
        assumptions=row.assumptions, previous_id=row.previous_id, reason=row.reason,
        idempotency_key=row.idempotency_key, actor_id=row.actor_id, created_at=explicit_utc_instant(row.created_at))
    if (result.assumptions.institute_id, result.assumptions.customer_id) != (result.institute_id, result.customer_id):
        raise business_error("Stored lifetime assumption scope is incoherent")
    return result

def owned(db, institute, customer):
    lock_institute(db, institute)
    return require_customer(db, institute, customer)

def head(db, institute, customer):
    return db.scalar(select(LifetimeHead).where(LifetimeHead.institute_id == institute, LifetimeHead.customer_id == customer)
        .execution_options(populate_existing=True))

def require(db, institute, customer, identifier):
    row = db.scalar(select(LifetimeOriginal).where(LifetimeOriginal.institute_id == institute,
        LifetimeOriginal.customer_id == customer, LifetimeOriginal.id == identifier))
    if row is None: raise not_found("Lifetime original not found")
    return snapshot(row)

def original(db, institute, customer, key):
    owned(db, institute, customer)
    row = db.scalar(select(LifetimeOriginal).where(LifetimeOriginal.institute_id == institute,
        LifetimeOriginal.customer_id == customer, LifetimeOriginal.idempotency_key == key))
    return snapshot(row) if row else None

def current(db, institute, customer):
    owned(db, institute, customer)
    pointer = head(db, institute, customer)
    return require(db, institute, customer, pointer.original_id) if pointer else None

def create(db, institute, customer, payload, actor):
    if not isinstance(actor,str) or not actor.strip() or len(actor)>160:
        raise business_error("A signed lifetime declaration actor is required")
    owned(db, institute, customer)
    row = db.scalar(select(LifetimeOriginal).where(LifetimeOriginal.institute_id == institute,
        LifetimeOriginal.customer_id == customer, LifetimeOriginal.idempotency_key == payload.idempotency_key))
    if row:
        old = snapshot(row)
        if old.actor_id != actor or old.model_dump(include=set(Declaration.model_fields)) != payload.model_dump():
            raise business_error("The key retains the original lifetime terms and actor")
        return old
    if (payload.assumptions.institute_id,payload.assumptions.customer_id) != (institute,customer):
        raise business_error("The lifetime declaration must match its owned customer")
    pointer = head(db, institute, customer)
    if payload.previous_id != (pointer.original_id if pointer else None):
        raise business_error("Lifetime assumptions changed; reread before declaring a correction")
    now = utcnow()
    if pointer and now < require(db,institute,customer,pointer.original_id).created_at:
        raise business_error("The lifetime clock precedes the original predecessor")
    row = LifetimeOriginal(id=new_id("crm_lifetime"), institute_id=institute, customer_id=customer,
        previous_id=payload.previous_id, assumptions=payload.assumptions.model_dump(mode="json"),
        reason=payload.reason, actor_id=actor, idempotency_key=payload.idempotency_key, created_at=now)
    db.add(row); db.flush()
    if pointer: pointer.original_id = row.id
    else: db.add(LifetimeHead(institute_id=institute,customer_id=customer,original_id=row.id))
    db.commit(); db.refresh(row)
    return snapshot(row)

class ScenarioRead(Fact):
    window: BillingWindow
    customer: RegisteredCustomerFact
    original: Original | None
    scenario: RemainingLifetimeScenario | None
    unavailable_reason: Literal["assumptions_absent", "future_assumptions", "future_registration"] | None

def read(db, institute, customer, start):
    registered = owned(db, institute, customer)
    registration = RegisteredCustomerFact(institute_id=institute,customer_id=customer,created_at=explicit_utc_instant(registered.created_at))
    now = utcnow()
    try: window = BillingWindow(institute_id=institute,customer_id=customer,start=start,end=now,captured_at=now)
    except ValidationError as error: raise business_error("An explicit positive observed lifetime window is required") from error
    pointer = head(db,institute,customer)
    retained = require(db,institute,customer,pointer.original_id) if pointer else None
    reason = "assumptions_absent" if retained is None else "future_assumptions" if retained.created_at > now else "future_registration" if registration.created_at>now else None
    result = None
    if reason is None:
        undated,future = db.execute(select(func.sum(case((QueueTicket.paid_at.is_(None),1),else_=0)),
            func.sum(case((QueueTicket.paid_at>now,1),else_=0))).where(QueueTicket.institute_id==institute,
                QueueTicket.customer_id==customer, QueueTicket.status=="paid")).one()
        result = calculate_remaining_lifetime(retained.assumptions,billing.capture(db,window),undated or 0,future or 0)
    return ScenarioRead(window=window,customer=registration,original=retained,scenario=result,unavailable_reason=reason)
