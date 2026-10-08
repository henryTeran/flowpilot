"""Explicit activation/revision/cancellation, with retained causal chains."""
from typing import Annotated, Literal
from pydantic import AwareDatetime, StringConstraints
from sqlalchemy import select
from app.modules.waitlist.domain import Fact
from app.modules.waitlist import originals
from app.modules.waitlist.models import LifecycleOriginal, DemandOriginal
from app.modules.crm.metrics import Identifier, Count
from app.modules.crm.policies import Reason, Key
from app.modules.customers.models import Customer
from app.modules.services.models import Service
from app.modules.employees.models import Employee
from app.modules.tickets.repository import lock_institute
from app.shared.ids import new_id
from app.shared.time import utcnow, explicit_utc_instant
from app.shared.exceptions import business_error, not_found

Fingerprint = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class Request(Fact):
    root_id: Identifier
    root_fingerprint: Fingerprint
    previous_id: Identifier | None
    previous_fingerprint: Fingerprint | None
    action: Literal["activate", "revise", "cancel"]
    target_id: Identifier
    target_fingerprint: Fingerprint
    reason: Reason
    idempotency_key: Key


class Event(Request):
    id: Identifier
    institute_id: Identifier
    actor_id: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    created_at: AwareDatetime
    activation_source: originals.Source | None
    effect: Literal["waitlist_state_only_no_booking_or_contact"] = "waitlist_state_only_no_booking_or_contact"


class State(Fact):
    root: originals.Envelope
    current_demand: originals.Envelope
    state: Literal["active", "cancelled"]
    events: tuple[originals.Envelope, ...]


class Audit(Fact):
    institute_id: Identifier
    captured_at: AwareDatetime
    offset: Count
    limit: Count
    total: Count
    active: Count
    cancelled: Count
    states: tuple[State, ...]


def _demand(db, institute, identifier, fingerprint, now):
    row = originals._row(db, institute, DemandOriginal.id, identifier)
    if row is None:
        raise business_error("Lifecycle references a missing retained demand")
    envelope = originals.verify(row, institute, now)
    if envelope.fingerprint != fingerprint:
        raise business_error("Lifecycle demand fingerprint changed")
    return envelope


def _chain(db, institute, root_id, now):
    rows = list(db.scalars(select(LifecycleOriginal).where(LifecycleOriginal.institute_id == institute,
        LifecycleOriginal.root_id == root_id).execution_options(populate_existing=True)))
    if not rows:
        return None
    try:
        successors = {}
        for row in rows:
            event = Event.model_validate(row.original)
            if originals.fingerprint(row.original) != row.fingerprint or \
                    (event.id, event.institute_id, event.root_id, event.previous_id or "", event.actor_id,
                     event.idempotency_key, event.created_at) != (row.id, institute, root_id, row.previous_id,
                     row.actor_id, row.idempotency_key, explicit_utc_instant(row.created_at)) \
                    or event.created_at > now or event.reason != row.original["reason"]:
                raise ValueError("Lifecycle original columns/clock/fingerprint mismatch")
            if any(value != value.strip() or any(ord(c) < 32 for c in value)
                    for value in (event.id, event.actor_id, event.idempotency_key)):
                raise ValueError("Lifecycle identities must remain exact")
            if row.previous_id in successors:
                raise ValueError("Lifecycle cannot branch")
            successors[row.previous_id] = (row, event)
        key, previous, root, current, state, history = "", None, None, None, None, []
        while key in successors:
            row, event = successors.pop(key)
            candidate_root = _demand(db, institute, root_id, event.root_fingerprint, now)
            target = _demand(db, institute, event.target_id, event.target_fingerprint, now)
            target_fact = originals.Original.model_validate(target.original)
            root_fact = originals.Original.model_validate(candidate_root.original)
            if target_fact.demand.customer_id != root_fact.demand.customer_id \
                    or max(target_fact.created_at, root_fact.created_at) > event.created_at:
                raise ValueError("Lifecycle must retain one owned customer and historical sources")
            if event.action == "cancel":
                if event.activation_source is not None:
                    raise ValueError("Cancellation does not recapture current eligibility")
            else:
                source = event.activation_source
                demand = target_fact.demand
                if source is None or source.registered_at > event.created_at \
                        or (source.customer_id, source.service_id, source.duration_minutes, source.allowed_employee_ids) != \
                           (demand.customer_id, demand.service_id, demand.duration_minutes, demand.allowed_employee_ids) \
                        or not any(window.end > event.created_at for window in demand.availability):
                    raise ValueError("Activation/revision requires retained current source and future availability")
            if previous is None:
                if event.action != "activate" or event.previous_id is not None or event.previous_fingerprint is not None \
                        or event.target_id != root_id:
                    raise ValueError("Lifecycle begins with explicit original activation")
                root = candidate_root
            elif state == "cancelled" or event.action == "activate" or event.previous_fingerprint != history[-1].fingerprint \
                    or event.created_at < previous.created_at or candidate_root != root:
                raise ValueError("Invalid lifecycle predecessor or terminal transition")
            if event.action == "cancel" and target != current or event.action == "revise" and target == current:
                raise ValueError("Cancellation preserves current demand; revision selects a new original")
            current, state = target, "cancelled" if event.action == "cancel" else "active"
            history.append(originals.Envelope(original=row.original, fingerprint=row.fingerprint))
            key, previous = event.id, event
        if successors or not history:
            raise ValueError("Lifecycle cannot contain orphan/cyclic events")
        return State(root=root, current_demand=current, state=state, events=tuple(history))
    except (ValueError, TypeError, KeyError, OverflowError) as error:
        raise business_error("Retained waitlist lifecycle requires verification") from error


def _current_source(db, institute, target, now):
    demand = originals.Original.model_validate(target.original).demand
    customer = db.scalar(select(Customer).where(Customer.institute_id == institute, Customer.id == demand.customer_id)
        .execution_options(populate_existing=True))
    service = db.scalar(select(Service).where(Service.id == demand.service_id, Service.status == "active")
        .execution_options(populate_existing=True))
    employees = set(db.scalars(select(Employee.id).where(Employee.institute_id == institute,
        Employee.id.in_(demand.allowed_employee_ids)))) if demand.allowed_employee_ids else set()
    if customer is None or explicit_utc_instant(customer.created_at) > now or service is None \
            or type(service.duration_min) is not int or service.duration_min != demand.duration_minutes \
            or employees != set(demand.allowed_employee_ids) or not any(window.end > now for window in demand.availability):
        raise business_error("Activation/revision requires current registration, duration, restrictions and future availability")
    return originals.Source(customer_id=customer.id, registered_at=explicit_utc_instant(customer.created_at),
        service_id=service.id, duration_minutes=service.duration_min, allowed_employee_ids=demand.allowed_employee_ids)


def create(db, institute, request: Request, actor):
    try:
        request = Request.model_validate(request.model_dump())
        if not isinstance(actor, str) or not actor or actor != actor.strip() or len(actor) > 160 or any(ord(c) < 32 for c in actor):
            raise ValueError("An explicit signed actor is required")
        lock_institute(db, institute)
        now = utcnow()
        replay = db.scalar(select(LifecycleOriginal).where(LifecycleOriginal.institute_id == institute,
            LifecycleOriginal.idempotency_key == request.idempotency_key).execution_options(populate_existing=True))
        if replay:
            state = _chain(db, institute, replay.root_id, now)
            receipt = next(envelope for envelope in state.events if envelope.original["id"] == replay.id)
            event = Event.model_validate(receipt.original)
            if Request.model_validate(event.model_dump(include=set(Request.model_fields))) != request or event.actor_id != actor:
                raise business_error("Lifecycle recovery key retains original request/actor")
            return receipt
        _demand(db, institute, request.root_id, request.root_fingerprint, now)
        target = _demand(db, institute, request.target_id, request.target_fingerprint, now)
        state = _chain(db, institute, request.root_id, now)
        previous = state.events[-1] if state else None
        if (request.previous_id, request.previous_fingerprint) != \
                ((previous.original["id"], previous.fingerprint) if previous else (None, None)):
            raise business_error("Waitlist version changed; reread before submitting")
        source = _current_source(db, institute, target, now) if request.action != "cancel" else None
        event = Event(**request.model_dump(), id=new_id("waitlist_event"), institute_id=institute,
            actor_id=actor, created_at=now, activation_source=source)
        raw = event.model_dump(mode="json")
        row = LifecycleOriginal(id=event.id, institute_id=institute, root_id=request.root_id,
            previous_id=request.previous_id or "", idempotency_key=request.idempotency_key, actor_id=actor,
            created_at=now, original=raw, fingerprint=originals.fingerprint(raw))
        db.add(row); db.flush()
        verified = _chain(db, institute, request.root_id, now)
        receipt = verified.events[-1]
        db.commit()
        return receipt
    except ValueError as error:
        db.rollback()
        raise business_error("Waitlist lifecycle request requires verification") from error
    except Exception:
        db.rollback()
        raise


def by_key(db, institute, key):
    if not isinstance(key, str) or not key or key != key.strip() or len(key) > 120:
        raise business_error("An exact lifecycle recovery key is required")
    lock_institute(db, institute)
    row = db.scalar(select(LifecycleOriginal).where(LifecycleOriginal.institute_id == institute,
        LifecycleOriginal.idempotency_key == key).execution_options(populate_existing=True))
    if row is None:
        return None
    state = _chain(db, institute, row.root_id, utcnow())
    return next(event for event in state.events if event.original["id"] == row.id)


def require(db, institute, identifier):
    lock_institute(db, institute)
    row = db.scalar(select(LifecycleOriginal).where(LifecycleOriginal.institute_id == institute,
        LifecycleOriginal.id == identifier).execution_options(populate_existing=True))
    if row is None:
        raise not_found("Retained waitlist lifecycle event not found")
    state = _chain(db, institute, row.root_id, utcnow())
    return next(event for event in state.events if event.original["id"] == row.id)


def read_state(db, institute, root_id):
    lock_institute(db, institute)
    state = _chain(db, institute, root_id, utcnow())
    if state is None:
        raise not_found("Activated waitlist demand not found")
    return state


def audit(db, institute, offset=0, limit=20):
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 50:
        raise business_error("Invalid lifecycle page bounds")
    lock_institute(db, institute)
    now = utcnow()
    root_ids = db.scalars(select(LifecycleOriginal.root_id).where(LifecycleOriginal.institute_id == institute)
        .distinct().order_by(LifecycleOriginal.root_id))
    states, total, active = [], 0, 0
    for root in root_ids:
        state = _chain(db, institute, root, now)
        active += state.state == "active"
        if offset <= total < offset+limit:
            states.append(state)
        total += 1
    return Audit(institute_id=institute, captured_at=now, offset=offset, limit=limit,
        total=total, active=active, cancelled=total-active, states=tuple(states))
