"""Atomic internal-event reconciliation originals; no outbound delivery."""
from typing import Literal
from pydantic import AwareDatetime, model_validator
from sqlalchemy import select, func, and_
from app.modules.crm import event_sources
from app.modules.crm.event_reconciliation import EventDecision, reconcile
from app.modules.crm.metrics import Fact, Identifier, Count
from app.modules.crm.models import EventCaptureOriginal, EventRevision, EventHead
from app.modules.crm.policies import Key, Reason
from app.modules.customers.repository import require_customer
from app.modules.tickets.repository import lock_institute
from app.shared.exceptions import business_error, not_found
from app.shared.ids import new_id
from app.shared.time import explicit_utc_instant


class Request(Fact):
    action: Literal["reconcile", "cancel", "process", "process_due"]
    event_key: Identifier | None
    expected_revision_id: Identifier | None
    reason: Reason
    idempotency_key: Key

    @model_validator(mode="after")
    def explicit_target(self):
        if self.action in {"reconcile","process_due"} and (self.event_key is not None or self.expected_revision_id is not None):
            raise ValueError("Batch actions have no explicit event target")
        if self.action in {"cancel","process"} and (self.event_key is None or self.expected_revision_id is None):
            raise ValueError("An explicit action requires the exact selected revision")
        return self


class RevisionRead(Fact):
    id: Identifier
    institute_id: Identifier
    customer_id: Identifier
    event_key: Identifier
    capture_id: Identifier
    previous_id: Identifier | None
    decision: EventDecision


class CaptureRead(Fact):
    id: Identifier
    institute_id: Identifier
    customer_id: Identifier
    actor_id: str
    request: Request
    captured_at: AwareDatetime
    source: event_sources.EventSourceRead
    revisions: tuple[RevisionRead, ...]


def owned(db,institute,customer):
    lock_institute(db,institute)
    require_customer(db,institute,customer)


def revision(row):
    result = RevisionRead.model_validate({name:getattr(row,name) for name in RevisionRead.model_fields})
    c = result.decision.candidate
    if (c.institute_id,c.customer_id,result.decision.event_key) != (result.institute_id,result.customer_id,result.event_key):
        raise business_error("Stored event revision scope is incoherent")
    return result


def selected(db,institute,customer):
    rows = db.execute(select(EventHead,EventRevision).outerjoin(EventRevision,and_(EventRevision.id==EventHead.revision_id,EventRevision.institute_id==EventHead.institute_id,EventRevision.customer_id==EventHead.customer_id,EventRevision.event_key==EventHead.event_key))
        .where(EventHead.institute_id==institute,EventHead.customer_id==customer)
        .order_by(EventHead.event_key).execution_options(populate_existing=True)).all()
    if any(row is None for _,row in rows): raise business_error("Stored event head scope is incoherent")
    return {head.event_key:(head,revision(row)) for head,row in rows}


def receipt(db,row):
    request = Request.model_validate(row.source["request"])
    source = event_sources.EventSourceRead.model_validate(row.source["capture"])
    if ((source.institute_id,source.customer_id) != (row.institute_id,row.customer_id)
        or source.captured_at != explicit_utc_instant(row.captured_at)
        or request.reason != row.reason or request.idempotency_key != row.idempotency_key):
        raise business_error("Stored event capture scope/terms are incoherent")
    revisions = []
    ids = row.source["selected_revision_ids"]
    if len(ids) != len(set(ids)): raise business_error("Stored event capture repeats a revision")
    for identifier in ids:
        value = db.scalar(select(EventRevision).where(EventRevision.institute_id==row.institute_id,
            EventRevision.customer_id==row.customer_id,EventRevision.id==identifier))
        if value is None: raise business_error("Stored event capture revision is unavailable")
        item = revision(value)
        if item.decision.evaluated_at > source.captured_at: raise business_error("Stored revision follows its capture")
        revisions.append(item)
    return CaptureRead(id=row.id,institute_id=row.institute_id,customer_id=row.customer_id,actor_id=row.actor_id,
        request=request,captured_at=source.captured_at,source=source,revisions=tuple(revisions))


def original(db,institute,customer,key):
    owned(db,institute,customer)
    row = db.scalar(select(EventCaptureOriginal).where(EventCaptureOriginal.institute_id==institute,
        EventCaptureOriginal.customer_id==customer,EventCaptureOriginal.idempotency_key==key))
    return receipt(db,row) if row else None


def semantic(decision):
    value = decision.model_dump(mode="json")
    value.pop("evaluated_at")
    value["candidate"].pop("captured_at")
    return value


def execute(db,institute,customer,payload,actor):
    owned(db,institute,customer)
    if not isinstance(actor,str) or not actor.strip() or len(actor)>160:
        raise business_error("A signed event actor is required")
    old = original(db,institute,customer,payload.idempotency_key)
    if old:
        if old.actor_id != actor or old.request != payload: raise business_error("The key retains original event terms and actor")
        return old
    current = selected(db,institute,customer)
    capture = event_sources.read(db,institute,customer)
    try: decisions = reconcile(capture,tuple(item.decision for _,item in current.values()))
    except ValueError as error: raise business_error("Event chronology/source requires verification") from error
    if payload.action == "cancel":
        target = current.get(payload.event_key)
        if target is None or target[1].id != payload.expected_revision_id:
            raise business_error("The event revision changed; reread before cancelling")
        if target[1].decision.state == "processed": raise business_error("A processed internal event cannot be cancelled")
        decisions = tuple(EventDecision(event_key=d.event_key,candidate=d.candidate,state="cancelled",
            reason="explicit_cancellation",evaluated_at=capture.captured_at) if d.event_key==payload.event_key else d for d in decisions)
    if payload.action in {"process","process_due"}:
        from app.modules.crm.event_worker import processing_keys
        if payload.action == "process":
            target = current.get(payload.event_key)
            if target is None or target[1].id != payload.expected_revision_id:
                raise business_error("The event revision changed; reread before processing")
            keys = {payload.event_key}
            if not any(d.event_key==payload.event_key and d.state=="due" for d in decisions):
                raise business_error("Only an event due in the fresh authoritative capture can be processed")
        else:
            keys = processing_keys(decisions)
        decisions = tuple(EventDecision(event_key=d.event_key,candidate=d.candidate,state="processed",
            reason="already_processed",evaluated_at=capture.captured_at) if d.event_key in keys else d for d in decisions)
    row = EventCaptureOriginal(id=new_id("crm_event_capture"),institute_id=institute,customer_id=customer,
        idempotency_key=payload.idempotency_key,actor_id=actor,reason=payload.reason,captured_at=capture.captured_at,
        source={"request":payload.model_dump(mode="json"),"capture":capture.model_dump(mode="json"),"selected_revision_ids":[]})
    try:
        db.add(row);db.flush()
        ids = []
        for decision in decisions:
            prior = current.get(decision.event_key)
            if prior and semantic(prior[1].decision)==semantic(decision):
                ids.append(prior[1].id);continue
            version = EventRevision(id=new_id("crm_event_revision"),institute_id=institute,customer_id=customer,
                event_key=decision.event_key,capture_id=row.id,previous_id=prior[1].id if prior else None,
                decision=decision.model_dump(mode="json"))
            db.add(version);db.flush();ids.append(version.id)
            if prior: prior[0].revision_id=version.id
            else: db.add(EventHead(institute_id=institute,customer_id=customer,event_key=decision.event_key,revision_id=version.id))
        row.source={**row.source,"selected_revision_ids":ids}
        db.flush()
        result=receipt(db,row)
        db.commit()
        return result
    except Exception:
        db.rollback();raise


class CurrentPage(Fact):
    institute_id: Identifier
    customer_id: Identifier
    total: Count
    offset: Count
    limit: Count
    revisions: tuple[RevisionRead, ...]


def page(db,institute,customer,limit=20,offset=0):
    owned(db,institute,customer)
    scope = (EventHead.institute_id==institute,EventHead.customer_id==customer)
    total = db.scalar(select(func.count()).select_from(EventHead).where(*scope))
    rows = db.scalars(select(EventRevision).join(EventHead,and_(EventRevision.id==EventHead.revision_id,EventRevision.institute_id==EventHead.institute_id,EventRevision.customer_id==EventHead.customer_id,EventRevision.event_key==EventHead.event_key))
        .where(*scope).order_by(EventHead.event_key).limit(limit).offset(offset)
        .execution_options(populate_existing=True))
    return CurrentPage(institute_id=institute,customer_id=customer,total=total,offset=offset,limit=limit,
        revisions=tuple(revision(row) for row in rows))


def require(db,institute,customer,identifier):
    owned(db,institute,customer)
    row = db.scalar(select(EventCaptureOriginal).where(EventCaptureOriginal.institute_id==institute,
        EventCaptureOriginal.customer_id==customer,EventCaptureOriginal.id==identifier))
    if row is None: raise not_found("Event capture original not found")
    return receipt(db,row)
