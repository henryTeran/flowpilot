"""Explicit signed manager decisions; no inferred proportional refund policy."""
from sqlalchemy import select
from app.modules.payments.models import PaymentIntent, RefundOutcome, RefundLoyaltyDecision
from app.modules.loyalty.models import LoyaltyEarning, LoyaltyEntry
from app.modules.loyalty.service import points as balance
from app.modules.payments.provider import identifier
from app.modules.tickets.repository import lock_institute
from app.shared.exceptions import business_error
from app.shared.ids import new_id
from app.shared.time import utcnow


def decide_refund_loyalty(db, institute_id, refund_id, delta, reason, key, actor):
    for value, limit in ((reason, 240), (key, 120), (actor, 160)):
        identifier(value, limit)
    if type(delta) is not int or not -1_000_000_000 <= delta <= 0:
        raise business_error("Correction entiere negative ou conservation explicite requise")
    lock_institute(db, institute_id)
    old = db.scalar(select(RefundLoyaltyDecision).where(RefundLoyaltyDecision.institute_id == institute_id,
                                                     RefundLoyaltyDecision.idempotency_key == key))
    if old is not None:
        if (old.refund_intent_id, old.points, old.reason, old.actor_id) != (refund_id, delta, reason, actor):
            raise business_error("Cette cle appartient a une autre decision de fidelite")
        return old
    intent = db.scalar(select(PaymentIntent).join(RefundOutcome, RefundOutcome.intent_id == PaymentIntent.id).where(
        PaymentIntent.id == refund_id, PaymentIntent.institute_id == institute_id,
        PaymentIntent.kind == "refund", RefundOutcome.status == "refunded"))
    if intent is None:
        raise business_error("Remboursement confirme de cet institut requis")
    if db.scalar(select(RefundLoyaltyDecision.id).where(RefundLoyaltyDecision.refund_intent_id == refund_id)):
        raise business_error("Ce remboursement possede deja une decision de fidelite")
    earning = db.get(LoyaltyEarning, intent.ticket_id)
    customer = earning.customer_id if earning else None
    previous = sum(db.scalars(select(RefundLoyaltyDecision.points).where(
        RefundLoyaltyDecision.institute_id == institute_id, RefundLoyaltyDecision.ticket_id == intent.ticket_id)), 0)
    if delta and (earning is None or -previous - delta > earning.points or balance(db, institute_id, customer) + delta < 0):
        raise business_error("Correction superieure aux points gagnes ou au solde disponible")
    now, decision_id = utcnow(), new_id("rld")
    entry_id = new_id("lp") if delta else None
    try:
        if entry_id:
            db.add(LoyaltyEntry(id=entry_id, institute_id=institute_id, customer_id=customer, points=delta,
                   reason=reason, actor_id=actor, occurred_at=now, idempotency_key="refund:" + decision_id))
            db.flush()
        row = RefundLoyaltyDecision(id=decision_id, institute_id=institute_id, refund_intent_id=refund_id,
            ticket_id=intent.ticket_id, customer_id=customer, entry_id=entry_id, points=delta,
            reason=reason, actor_id=actor, idempotency_key=key, decided_at=now)
        db.add(row)
        db.commit()
        db.refresh(row)
        return row
    except Exception:
        db.rollback()
        raise
