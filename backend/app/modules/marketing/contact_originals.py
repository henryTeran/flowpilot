"""Owned immutable marketing contact declarations and protected original replay."""
from pydantic import ValidationError
from sqlalchemy import select

from app.modules.crm.segments import RegisteredCustomerFact
from app.modules.customers.repository import require_customer
from app.modules.marketing import contacts
from app.modules.marketing.models import ContactHead, ContactOriginal
from app.modules.tickets.repository import lock_institute
from app.shared.exceptions import business_error, not_found
from app.shared.ids import new_id
from app.shared.time import explicit_utc_instant, utcnow


def owned(db, institute, customer):
    lock_institute(db, institute)
    return require_customer(db, institute, customer)


def receipt(row):
    try:
        result = contacts.Original(id=row.id, previous_id=row.previous_id, actor_id=row.actor_id,
            created_at=explicit_utc_instant(row.created_at), declaration=row.declaration,
            reason=row.reason, idempotency_key=row.idempotency_key)
    except (ValidationError, ValueError) as error:
        raise business_error("Stored marketing contact original is incoherent") from error
    if (result.declaration.institute_id, result.declaration.customer_id) != (row.institute_id, row.customer_id):
        raise business_error("Stored marketing contact original ownership is incoherent")
    if result.reason != row.reason or result.idempotency_key != row.idempotency_key:
        raise business_error("Stored marketing contact original terms are incoherent")
    return result


def head(db, institute, customer):
    return db.scalar(select(ContactHead).where(ContactHead.institute_id == institute, ContactHead.customer_id == customer)
        .execution_options(populate_existing=True))


def require(db, institute, customer, identifier):
    owned(db, institute, customer)
    row = db.scalar(select(ContactOriginal).where(ContactOriginal.institute_id == institute,
        ContactOriginal.customer_id == customer, ContactOriginal.id == identifier).execution_options(populate_existing=True))
    if row is None: raise not_found("Marketing contact original not found")
    return receipt(row)


def original(db, institute, customer, key):
    owned(db, institute, customer)
    # Key scope is the institute, not just the requested customer. Do not reveal
    # another customer's contact, but refuse its key rather than attempting reuse.
    row = db.scalar(select(ContactOriginal).where(ContactOriginal.institute_id == institute,
        ContactOriginal.idempotency_key == key).execution_options(populate_existing=True))
    if row is None: return None
    if row.customer_id != customer: raise business_error("Marketing contact key belongs to another customer")
    return receipt(row)


def current(db, institute, customer):
    owned(db, institute, customer)
    pointer = head(db, institute, customer)
    return require(db, institute, customer, pointer.original_id) if pointer else None


def create(db, institute, customer, payload, actor):
    payload = contacts.Request.model_validate(payload.model_dump())
    if not isinstance(actor, str) or not actor.strip() or actor != actor.strip() or len(actor) > 160:
        raise business_error("A signed marketing contact actor is required")
    registered = owned(db, institute, customer)
    if (payload.declaration.institute_id, payload.declaration.customer_id) != (institute, customer):
        raise business_error("Marketing contact declaration must match the owned customer")
    old = original(db, institute, customer, payload.idempotency_key)
    if old is not None:
        if old.actor_id != actor or contacts.Request.model_validate(old.model_dump(include=set(contacts.Request.model_fields))) != payload:
            raise business_error("Marketing contact key retains original terms and actor")
        return old
    pointer = head(db, institute, customer)
    previous = require(db, institute, customer, pointer.original_id) if pointer else None
    registration = RegisteredCustomerFact(institute_id=institute, customer_id=customer, created_at=explicit_utc_instant(registered.created_at))
    try:
        result = contacts.record(new_id("marketing_contact"), actor, registration, payload, previous, utcnow())
    except ValueError as error:
        raise business_error("Marketing contact changed or source clock precedes its owned predecessor") from error
    row = ContactOriginal(id=result.id, institute_id=institute, customer_id=customer, previous_id=result.previous_id,
        actor_id=result.actor_id, reason=result.reason, idempotency_key=result.idempotency_key, created_at=result.created_at,
        declaration=result.declaration.model_dump(mode="json"))
    try:
        db.add(row); db.flush()
        if pointer: pointer.original_id = row.id
        else: db.add(ContactHead(institute_id=institute, customer_id=customer, original_id=row.id))
        db.flush()
        retained = receipt(row)
        db.commit()
        return retained
    except Exception:
        db.rollback()
        raise
