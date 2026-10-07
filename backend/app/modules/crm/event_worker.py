"""Bounded internal event processing selection, without any message transport."""
import logging
from datetime import timezone
from app.modules.crm.event_reconciliation import EventDecision

logger = logging.getLogger(__name__)

BATCH_SIZE = 20  # Operational work bound, not a commercial/calendar default.


def processing_keys(decisions: tuple[EventDecision, ...]) -> set[str]:
    eligible = sorted((d for d in decisions if d.state == "due"),
        key=lambda d: (d.candidate.due_at.astimezone(timezone.utc),d.event_key))
    return {d.event_key for d in eligible[:BATCH_SIZE]}


from hashlib import sha256
import json
from app.modules.crm.metrics import Fact, Identifier
from app.modules.crm.policies import Key, Reason
from app.modules.customers.models import Customer
from app.modules.tickets.repository import lock_institute
from app.shared.exceptions import business_error
from sqlalchemy import select


class PassRequest(Fact):
    after: Identifier | None
    reason: Reason
    idempotency_key: Key


class PassItem(Fact):
    customer_id: Identifier
    capture_id: Identifier | None
    failed: bool


class PassRead(Fact):
    institute_id: Identifier
    after: Identifier | None
    next_after: Identifier | None
    items: tuple[PassItem, ...]


def dispatch(session_factory,institute,payload,actor):
    """One bounded keyset page; each customer's receipt is independently atomic.

    Repeating a pass key replays committed customer receipts, including after a
    response loss. Page membership is a fresh scan, not an immutable batch manifest.
    Newly registered earlier IDs are picked up by the next complete scan.
    """
    from app.modules.crm import event_ledger
    if not isinstance(actor,str) or not actor.strip() or len(actor)>160:
        raise business_error("A signed worker actor is required")
    with session_factory() as db:
        lock_institute(db,institute)
        query=select(Customer.id).where(Customer.institute_id==institute)
        if payload.after is not None:query=query.where(Customer.id>payload.after)
        ids=list(db.scalars(query.order_by(Customer.id).limit(51)))
    more=len(ids)>50;ids=ids[:50];items=[]
    for customer in ids:
        key=sha256(json.dumps(["crm-worker-pass-v1",institute,customer,payload.idempotency_key],separators=(",",":")).encode()).hexdigest()
        request=event_ledger.Request(action="process_due",event_key=None,expected_revision_id=None,
            reason=payload.reason,idempotency_key=key)
        with session_factory() as db:
            try:
                result=event_ledger.execute(db,institute,customer,request,actor)
                items.append(PassItem(customer_id=customer,capture_id=result.id,failed=False))
            except Exception as error:
                db.rollback()
                logger.warning("CRM worker customer processing failed",extra={"institute_id":institute,
                    "customer_id":customer,"error_type":type(error).__name__})
                items.append(PassItem(customer_id=customer,capture_id=None,failed=True))
    return PassRead(institute_id=institute,after=payload.after,next_after=ids[-1] if more else None,items=tuple(items))
