"""Registered-customer immutable lifecycle declarations and birthday reads."""
from typing import Annotated, Literal
from pydantic import AwareDatetime, StringConstraints
from sqlalchemy import select
from app.modules.crm import calendar_policies
from app.modules.crm.lifecycle import LifecycleDeclaration, BirthdayCapture, BirthdayObservation, observe_birthday
from app.modules.crm.metrics import Fact, Identifier
from app.modules.crm.models import LifecycleHead, LifecycleOriginal
from app.modules.crm.policies import Reason, Key
from app.modules.crm.segments import RegisteredCustomerFact
from app.modules.customers.repository import require_customer
from app.modules.tickets.repository import lock_institute
from app.shared.exceptions import business_error, not_found
from app.shared.ids import new_id
from app.shared.time import explicit_utc_instant, utcnow

class Declaration(Fact):
    declaration: LifecycleDeclaration
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
        declaration=row.declaration, previous_id=row.previous_id, reason=row.reason,
        idempotency_key=row.idempotency_key, actor_id=row.actor_id, created_at=explicit_utc_instant(row.created_at))
    if (result.declaration.institute_id, result.declaration.customer_id) != (result.institute_id, result.customer_id):
        raise business_error("Stored lifecycle assumption scope is incoherent")
    return result

def owned(db, institute, customer):
    lock_institute(db, institute)
    return require_customer(db, institute, customer)

def head(db, institute, customer):
    return db.scalar(select(LifecycleHead).where(LifecycleHead.institute_id == institute, LifecycleHead.customer_id == customer)
        .execution_options(populate_existing=True))

def require(db, institute, customer, identifier):
    row = db.scalar(select(LifecycleOriginal).where(LifecycleOriginal.institute_id == institute,
        LifecycleOriginal.customer_id == customer, LifecycleOriginal.id == identifier))
    if row is None: raise not_found("Lifecycle original not found")
    return snapshot(row)


class LifecycleRead(Fact):
    institute_id: Identifier
    customer_id: Identifier
    captured_at: AwareDatetime
    customer: RegisteredCustomerFact
    original: Original | None
    calendar_original: calendar_policies.PolicyRead | None
    birthday: BirthdayObservation | None
    unavailable_reason: Literal["declaration_absent","calendar_absent","future_declaration","future_calendar","future_registration"] | None
    external_message_sent: Literal[False] = False
    delivery_authorized: Literal[False] = False


def read(db, institute, customer, *, _captured_at=None):
    registered = owned(db,institute,customer)
    registration = RegisteredCustomerFact(institute_id=institute,customer_id=customer,created_at=explicit_utc_instant(registered.created_at))
    pointer = head(db,institute,customer)
    retained = require(db,institute,customer,pointer.original_id) if pointer else None
    calendar_head = calendar_policies.read_head(db,institute)
    calendar = calendar_policies.require(db,institute,calendar_head.policy_id) if calendar_head else None
    now = _captured_at if _captured_at is not None else utcnow()
    reason = "declaration_absent" if retained is None else "calendar_absent" if calendar is None else "future_declaration" if retained.created_at>now else "future_calendar" if calendar.created_at>now else "future_registration" if registration.created_at>now else None
    observation = None
    if reason is None:
        try:
            observation = observe_birthday(retained.declaration,calendar.policy,registration,
                BirthdayCapture(institute_id=institute,customer_id=customer,captured_at=now))
        except ValueError as error:
            raise business_error("Birthday source/calendar cannot establish a valid observation") from error
    return LifecycleRead(institute_id=institute,customer_id=customer,captured_at=now,customer=registration,
        original=retained,calendar_original=calendar,birthday=observation,unavailable_reason=reason)

def original(db, institute, customer, key):
    owned(db, institute, customer)
    row = db.scalar(select(LifecycleOriginal).where(LifecycleOriginal.institute_id == institute,
        LifecycleOriginal.customer_id == customer, LifecycleOriginal.idempotency_key == key))
    return snapshot(row) if row else None

def current(db, institute, customer):
    owned(db, institute, customer)
    pointer = head(db, institute, customer)
    return require(db, institute, customer, pointer.original_id) if pointer else None

def create(db, institute, customer, payload, actor):
    if not isinstance(actor,str) or not actor.strip() or len(actor)>160:
        raise business_error("A signed lifecycle declaration actor is required")
    owned(db, institute, customer)
    row = db.scalar(select(LifecycleOriginal).where(LifecycleOriginal.institute_id == institute,
        LifecycleOriginal.customer_id == customer, LifecycleOriginal.idempotency_key == payload.idempotency_key))
    if row:
        old = snapshot(row)
        if old.actor_id != actor or old.model_dump(include=set(Declaration.model_fields)) != payload.model_dump():
            raise business_error("The key retains the original lifecycle terms and actor")
        return old
    if (payload.declaration.institute_id,payload.declaration.customer_id) != (institute,customer):
        raise business_error("The lifecycle declaration must match its owned customer")
    pointer = head(db, institute, customer)
    if payload.previous_id != (pointer.original_id if pointer else None):
        raise business_error("Lifecycle declaration changed; reread before declaring a correction")
    now = utcnow()
    if pointer and now < require(db,institute,customer,pointer.original_id).created_at:
        raise business_error("The lifecycle clock precedes the original predecessor")
    row = LifecycleOriginal(id=new_id("crm_lifecycle"), institute_id=institute, customer_id=customer,
        previous_id=payload.previous_id, declaration=payload.declaration.model_dump(mode="json"),
        reason=payload.reason, actor_id=actor, idempotency_key=payload.idempotency_key, created_at=now)
    db.add(row); db.flush()
    if pointer: pointer.original_id = row.id
    else: db.add(LifecycleHead(institute_id=institute,customer_id=customer,original_id=row.id))
    db.commit(); db.refresh(row)
    return snapshot(row)
