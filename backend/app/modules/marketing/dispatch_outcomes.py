"""Trusted adapter outcome retention; public routes may read, never fabricate results."""
from pydantic import AwareDatetime
from sqlalchemy import select, func
from app.modules.crm.metrics import Fact, Identifier
from app.modules.crm.policies import Reason, Key
from app.modules.marketing import dispatch_intents, provider, catalogs
from app.modules.marketing.models import DispatchOutcome, DispatchHead
from app.shared.exceptions import business_error, not_found
from app.shared.ids import new_id
from app.shared.time import explicit_utc_instant, utcnow

class Request(Fact):
    intent_id: Identifier
    expected_previous_id: Identifier | None
    result: provider.Result
    reason: Reason
    idempotency_key: Key

class Original(Fact):
    id: Identifier
    actor_id: provider.Exact
    request: Request
    created_at: AwareDatetime

def coherent(previous, result, at):
    if result.observed_at > at: raise ValueError("Provider observation is future to retention clock")
    if previous is not None:
        if previous.request.result.status != "unknown": raise ValueError("Terminal submission outcome cannot be replaced")
        if at < previous.created_at or result.observed_at < previous.request.result.observed_at: raise ValueError("Outcome clocks must be monotonic")
        reference = previous.request.result.provider_message_id
        if reference is not None and result.provider_message_id != reference: raise ValueError("Known provider reference cannot change")

def receipt(db, row, intent):
    try:
        request = Request(intent_id=row.intent_id, expected_previous_id=row.previous_id, result=row.result, reason=row.reason, idempotency_key=row.idempotency_key)
        result = provider.validate_result(intent.submission, request.result)
        at = explicit_utc_instant(row.created_at)
        if row.institute_id != intent.submission.account.institute_id or row.intent_id != intent.id or at < intent.created_at:
            raise ValueError("Outcome ownership/clock differs from intent")
        if request.reason != row.reason or request.idempotency_key != row.idempotency_key or row.previous_id == row.id:
            raise ValueError("Outcome terms/predecessor are incoherent")
        if row.actor_id != row.actor_id.strip() or any(ord(c) < 32 or ord(c) == 127 for c in row.actor_id): raise ValueError("Exact retained worker actor required")
        coherent(None, result, at)
        return Original(id=row.id, actor_id=row.actor_id, request=request, created_at=at)
    except ValueError as error: raise business_error("Stored dispatch outcome is incoherent") from error

def row_by_id(db, institute, intent, identifier):
    row = db.scalar(select(DispatchOutcome).where(DispatchOutcome.institute_id == institute, DispatchOutcome.intent_id == intent,
        DispatchOutcome.id == identifier).execution_options(populate_existing=True))
    if row is None: raise not_found("Dispatch outcome not found")
    return row

def require(db, institute, intent_id, identifier):
    intent = dispatch_intents.require(db, institute, intent_id)
    row = row_by_id(db, institute, intent_id, identifier)
    result = receipt(db, row, intent)
    if row.previous_id is not None:
        previous = receipt(db, row_by_id(db, institute, intent_id, row.previous_id), intent)
        if previous.request.expected_previous_id == row.id: raise business_error("Stored outcome predecessor cycle")
        try: coherent(previous, result.request.result, result.created_at)
        except ValueError as error: raise business_error("Stored outcome predecessor is incoherent") from error
    return result

def original(db, institute, intent_id, key):
    dispatch_intents.require(db, institute, intent_id)
    row = db.scalar(select(DispatchOutcome).where(DispatchOutcome.institute_id == institute, DispatchOutcome.idempotency_key == key).execution_options(populate_existing=True))
    if row is None: return None
    if row.intent_id != intent_id: raise business_error("Outcome key belongs to another intent")
    return require(db, institute, intent_id, row.id)

def head(db, institute, intent_id):
    return db.scalar(select(DispatchHead).where(DispatchHead.institute_id == institute, DispatchHead.intent_id == intent_id).execution_options(populate_existing=True))

def current(db, institute, intent_id):
    dispatch_intents.require(db, institute, intent_id)
    pointer = head(db, institute, intent_id)
    return require(db, institute, intent_id, pointer.original_id) if pointer else None

def append(db, institute, payload, actor):
    """Internal trusted-worker entry point. Never expose as client-writable HTTP API."""
    payload = Request.model_validate(payload.model_dump())
    intent = dispatch_intents.require(db, institute, payload.intent_id)
    old = original(db, institute, payload.intent_id, payload.idempotency_key)
    if old is not None:
        if old.request != payload or old.actor_id != actor: raise business_error("Outcome key retains original terms and actor")
        return old
    previous = current(db, institute, payload.intent_id)
    if payload.expected_previous_id != (previous.id if previous else None): raise business_error("Exact current outcome predecessor required")
    try:
        result = provider.validate_result(intent.submission, payload.result)
        at = utcnow(); coherent(previous, result, at)
        if at < intent.created_at: raise ValueError("Retention clock precedes intent")
        if not isinstance(actor, str) or not actor or actor != actor.strip() or len(actor) > 160 or any(ord(c) < 32 or ord(c) == 127 for c in actor):
            raise ValueError("Exact worker actor required")
    except ValueError as error: raise business_error("Outcome does not match retained intent or predecessor") from error
    pointer = head(db, institute, payload.intent_id)
    row = DispatchOutcome(id=new_id("marketing_outcome"), institute_id=institute, intent_id=payload.intent_id, previous_id=payload.expected_previous_id,
        actor_id=actor, reason=payload.reason, idempotency_key=payload.idempotency_key, created_at=at, result=result.model_dump(mode="json"))
    try:
        db.add(row); db.flush()
        if pointer: pointer.original_id = row.id
        else: db.add(DispatchHead(institute_id=institute, intent_id=payload.intent_id, original_id=row.id))
        db.flush(); retained = require(db, institute, payload.intent_id, row.id); db.commit(); return retained
    except Exception: db.rollback(); raise

def audit(db, institute, intent_id, offset=0, limit=20):
    catalogs.bounds(db, institute, offset, limit); dispatch_intents.require(db, institute, intent_id)
    scope = (DispatchOutcome.institute_id == institute, DispatchOutcome.intent_id == intent_id)
    total = db.scalar(select(func.count()).select_from(DispatchOutcome).where(*scope))
    rows = db.scalars(select(DispatchOutcome).where(*scope).order_by(DispatchOutcome.created_at, DispatchOutcome.id).offset(offset).limit(limit))
    items = tuple(require(db, institute, intent_id, row.id) for row in rows)
    present = {o.id: o.request.expected_previous_id for o in items}
    for identifier in present:
        seen = set()
        while identifier in present:
            if identifier in seen: raise business_error("Stored audit predecessor cycle")
            seen.add(identifier); identifier = present[identifier]
    return catalogs.Page[Original](institute_id=institute, total=total, offset=offset, limit=limit, items=items)
