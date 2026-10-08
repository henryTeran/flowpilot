"""Retained declarations; replay precedes mutable customer/catalog recapture."""
from hashlib import sha256
import json
from typing import Annotated, Literal
from pydantic import AwareDatetime, Field, StringConstraints, model_validator
from sqlalchemy import select
from app.modules.waitlist.domain import Fact, Demand, Window, Minutes, Text
from app.modules.crm.metrics import Identifier, Count
from app.modules.crm.policies import Reason, Key
from app.modules.waitlist.models import DemandOriginal
from app.modules.customers.models import Customer
from app.modules.services.models import Service
from app.modules.employees.models import Employee
from app.modules.tickets.repository import lock_institute
from app.shared.exceptions import business_error, not_found
from app.shared.time import utcnow, explicit_utc_instant
from app.shared.ids import new_id


class Request(Fact):
    customer_id: Identifier
    service_id: Identifier
    duration_minutes: Minutes
    availability: tuple[Window, ...] = Field(min_length=1, max_length=64)
    allowed_employee_ids: tuple[Identifier, ...] = Field(max_length=100)
    constraints_review: Literal["confirmed", "unknown"]
    availability_evidence: Text
    constraints_evidence: Text | None
    reason: Reason
    idempotency_key: Key


class Source(Fact):
    customer_id: Identifier
    registered_at: AwareDatetime
    service_id: Identifier
    duration_minutes: Minutes
    allowed_employee_ids: tuple[Identifier, ...]


class Original(Fact):
    id: Identifier
    institute_id: Identifier
    actor_id: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    created_at: AwareDatetime
    idempotency_key: Key
    reason: Reason
    demand: Demand
    source: Source
    state: Literal["declared_only"] = "declared_only"
    action: Literal["no_booking_or_contact"] = "no_booking_or_contact"

    @model_validator(mode="after")
    def coherent(self):
        if self.demand.institute_id != self.institute_id or self.demand.declared_at != self.created_at \
                or self.source.registered_at > self.created_at \
                or (self.source.customer_id, self.source.service_id, self.source.duration_minutes, self.source.allowed_employee_ids) != \
                   (self.demand.customer_id, self.demand.service_id, self.demand.duration_minutes, self.demand.allowed_employee_ids):
            raise ValueError("Demand must bind owned registration/catalog/restrictions at capture")
        if any(value != value.strip() or any(ord(c) < 32 for c in value)
                for value in (self.id, self.actor_id, self.idempotency_key)):
            raise ValueError("Original identity, actor and key must remain exact")
        return self


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
    basis: Literal["verified_retained_declarations_not_active_waitlist"] = "verified_retained_declarations_not_active_waitlist"


def fingerprint(raw):
    return sha256(json.dumps(raw, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode("ascii")).hexdigest()


def verify(row, institute, now):
    try:
        if row.institute_id != institute or fingerprint(row.original) != row.fingerprint:
            raise ValueError("Original ownership/fingerprint mismatch")
        original = Original.model_validate(row.original)
        if (original.id, original.institute_id, original.demand.customer_id, original.actor_id,
                original.created_at, original.idempotency_key) != (row.id, institute, row.customer_id,
                row.actor_id, explicit_utc_instant(row.created_at), row.idempotency_key) or original.created_at > now:
            raise ValueError("Original columns/capture mismatch")
        if original.reason != row.original["reason"] or original.idempotency_key != row.original["idempotency_key"]:
            raise ValueError("Stored declarations must remain exact")
        return Envelope(original=row.original, fingerprint=row.fingerprint)
    except (ValueError, TypeError, KeyError, OverflowError) as error:
        raise business_error("Retained waitlist demand requires verification") from error


def _row(db, institute, field, value):
    return db.scalar(select(DemandOriginal).where(DemandOriginal.institute_id == institute, field == value)
        .execution_options(populate_existing=True))


def by_key(db, institute, key):
    if not isinstance(key, str) or not key or key != key.strip() or len(key) > 120:
        raise business_error("An exact recovery key is required")
    lock_institute(db, institute)
    row = _row(db, institute, DemandOriginal.idempotency_key, key)
    return verify(row, institute, utcnow()) if row else None


def require(db, institute, identifier):
    lock_institute(db, institute)
    row = _row(db, institute, DemandOriginal.id, identifier)
    if row is None:
        raise not_found("Retained waitlist demand not found")
    return verify(row, institute, utcnow())


def create(db, institute, request: Request, actor):
    try:
        request = Request.model_validate(request.model_dump())
        if not isinstance(actor, str) or not actor or actor != actor.strip() or len(actor) > 160 or any(ord(c) < 32 for c in actor):
            raise ValueError("An explicit signed actor is required")
        lock_institute(db, institute)
        now = utcnow()
        row = _row(db, institute, DemandOriginal.idempotency_key, request.idempotency_key)
        if row:
            envelope = verify(row, institute, now)
            old = Original.model_validate(envelope.original)
            replay = Request(**old.demand.model_dump(exclude={"institute_id", "declared_at"}),
                reason=old.reason, idempotency_key=old.idempotency_key)
            if replay != request or old.actor_id != actor:
                raise business_error("The recovery key retains its original declaration and actor")
            return envelope
        demand = Demand(**request.model_dump(exclude={"reason", "idempotency_key"}), institute_id=institute, declared_at=now)
        customer = db.scalar(select(Customer).where(Customer.id == demand.customer_id, Customer.institute_id == institute)
            .execution_options(populate_existing=True))
        service = db.scalar(select(Service).where(Service.id == demand.service_id, Service.status == "active")
            .execution_options(populate_existing=True))
        if customer is None or service is None:
            raise not_found("Registered customer or active service not found")
        if type(service.duration_min) is not int or service.duration_min != demand.duration_minutes:
            raise business_error("Current service duration requires a new declaration")
        employees = tuple(db.scalars(select(Employee.id).where(Employee.institute_id == institute,
            Employee.id.in_(demand.allowed_employee_ids)))) if demand.allowed_employee_ids else ()
        if set(employees) != set(demand.allowed_employee_ids):
            raise business_error("Employee restrictions require owned identities")
        original = Original(id=new_id("waitlist_demand"), institute_id=institute, actor_id=actor, created_at=now,
            idempotency_key=request.idempotency_key, reason=request.reason, demand=demand,
            source=Source(customer_id=customer.id, registered_at=explicit_utc_instant(customer.created_at),
                service_id=service.id, duration_minutes=service.duration_min, allowed_employee_ids=demand.allowed_employee_ids))
        raw = original.model_dump(mode="json")
        row = DemandOriginal(id=original.id, institute_id=institute, customer_id=customer.id,
            actor_id=actor, created_at=now, idempotency_key=request.idempotency_key, original=raw, fingerprint=fingerprint(raw))
        db.add(row); db.flush()
        result = verify(row, institute, now)
        db.commit()
        return result
    except ValueError as error:
        db.rollback()
        raise business_error("Waitlist declaration or source requires verification") from error
    except Exception:
        db.rollback()
        raise


def audit(db, institute, offset=0, limit=20):
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 50:
        raise business_error("Invalid demand audit page bounds")
    lock_institute(db, institute)
    now = utcnow()
    rows, total = [], 0
    for row in db.scalars(select(DemandOriginal).where(DemandOriginal.institute_id == institute)
            .order_by(DemandOriginal.created_at, DemandOriginal.id).execution_options(yield_per=100, populate_existing=True)):
        envelope = verify(row, institute, now)
        if offset <= total < offset+limit:
            rows.append(envelope)
        total += 1
    return Audit(institute_id=institute, captured_at=now, offset=offset, limit=limit, total=total, originals=tuple(rows))
