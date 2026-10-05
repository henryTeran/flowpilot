"""Atomic point spending and reversible service pricing before checkout closure."""
from decimal import Decimal
from sqlalchemy import select
from app.modules.loyalty.models import LoyaltyEntry, LoyaltyReward, LoyaltyRedemption
from app.modules.loyalty.service import points
from app.modules.customers.repository import require_customer
from app.modules.memberships.benefits import checkout_line, update_total
from app.modules.tickets.models import TicketLine
from app.modules.tickets.repository import lock_institute
from app.modules.tickets.events import record_event
from app.shared.exceptions import business_error, not_found
from app.shared.ids import new_id
from app.shared.time import utcnow


def require_no_reward(db, ticket=None, line_id=None, history=False):
    query = select(LoyaltyRedemption.id)
    if line_id:
        query = query.where(LoyaltyRedemption.ticket_line_id == line_id)
    else:
        query = query.join(TicketLine, LoyaltyRedemption.ticket_line_id == TicketLine.id).where(TicketLine.ticket_id == ticket.id)
    if not history:
        query = query.where(LoyaltyRedemption.reversed_at.is_(None))
    if db.scalar(query):
        raise business_error("L'historique des recompenses interdit la suppression de prestation" if history
                             else "Annuler la recompense active avant cette modification")


def apply(db, institute, identifier, payload, actor):
    lock_institute(db, institute)
    old = db.scalar(select(LoyaltyRedemption).where(LoyaltyRedemption.institute_id == institute,
                                                  LoyaltyRedemption.idempotency_key == payload.idempotency_key))
    if old:
        if (old.reward_id, old.ticket_line_id) != (identifier, payload.ticket_line_id):
            raise business_error("Cette cle appartient a une autre utilisation de recompense")
        return old
    reward = db.scalar(select(LoyaltyReward).where(LoyaltyReward.institute_id == institute, LoyaltyReward.id == identifier))
    if reward is None:
        raise not_found("Recompense introuvable")
    ticket, line = checkout_line(db, institute, payload.ticket_line_id)
    require_customer(db, institute, ticket.customer_id)
    from app.modules.tickets.currency import require_current_catalog_currency
    require_current_catalog_currency(db, ticket)
    if ticket.currency != reward.currency or line.service_id != reward.service_id or not line.performed_by_employee_id:
        raise business_error("Cliente, devise et prestation realisee correspondantes requises")
    from app.modules.commerce.models import PackageRedemption
    from app.modules.memberships.models import MembershipBenefit
    for model in (PackageRedemption, MembershipBenefit, LoyaltyRedemption):
        if db.scalar(select(model.id).where(model.ticket_line_id == line.id, model.reversed_at.is_(None))):
            raise business_error("Une couverture est deja active pour cette prestation")
    if line.quantity <= 0 or line.unit_price is None or line.total is None:
        raise business_error("Prix et quantite valides requis")
    price, total = Decimal(str(line.unit_price)), Decimal(str(line.total))
    if not price.is_finite() or not total.is_finite():
        raise business_error("Prix valides requis")
    reduced_price = max(Decimal("0"), price - reward.discount_amount)
    reduced_total = (reduced_price * line.quantity).quantize(Decimal("0.01"))
    if reduced_price >= price or reduced_total >= total:
        raise business_error("La recompense doit reduire le montant de la prestation")
    cost = reward.points_cost * line.quantity
    balance = points(db, institute, ticket.customer_id)
    if balance < cost or balance < reward.minimum_points:
        raise business_error("Solde ou niveau de points insuffisant")
    now, entry_id = utcnow(), new_id("lp")
    db.add(LoyaltyEntry(id=entry_id, institute_id=institute, customer_id=ticket.customer_id,
        points=-cost, reason="Utilisation de recompense", actor_id=actor, occurred_at=now,
        idempotency_key=f"reward:{entry_id}"))
    db.flush()
    row = LoyaltyRedemption(id=new_id("lrd"), institute_id=institute, customer_id=ticket.customer_id,
        reward_id=reward.id, ticket_line_id=line.id, entry_id=entry_id, quantity=line.quantity,
        points_cost=cost, currency=reward.currency, original_unit_price=price, original_total=total,
        reward_unit_price=reduced_price, reward_total=reduced_total, actor_id=actor, occurred_at=now,
        idempotency_key=payload.idempotency_key)
    line.unit_price, line.total = reduced_price, reduced_total
    db.add(row)
    update_total(db, ticket)
    record_event(db, ticket, "commerce.loyalty_redeemed", ticket.status, line.performed_by_employee_id)
    db.commit()
    db.refresh(row)
    return row


def reverse(db, institute, identifier, reason, actor):
    lock_institute(db, institute)
    row = db.scalar(select(LoyaltyRedemption).where(LoyaltyRedemption.institute_id == institute, LoyaltyRedemption.id == identifier))
    if row is None:
        raise not_found("Utilisation de recompense introuvable")
    db.refresh(row)
    if row.reversed_at:
        if row.reversal_reason != reason:
            raise business_error("Recompense deja annulee avec un autre motif")
        return row
    ticket, line = checkout_line(db, institute, row.ticket_line_id)
    if ticket.customer_id != row.customer_id or line.unit_price != row.reward_unit_price or line.total != row.reward_total:
        raise business_error("Historique de recompense incoherent")
    if points(db, institute, row.customer_id) + row.points_cost > 1_000_000_000_000:
        raise business_error("Limite du solde de points depassee")
    now, entry_id = utcnow(), new_id("lp")
    db.add(LoyaltyEntry(id=entry_id, institute_id=institute, customer_id=row.customer_id,
        points=row.points_cost, reason=reason, actor_id=actor, occurred_at=now,
        idempotency_key=f"reward-reversal:{entry_id}"))
    db.flush()
    row.reversed_at, row.reversed_by, row.reversal_reason, row.reversal_entry_id = now, actor, reason, entry_id
    line.unit_price, line.total = row.original_unit_price, row.original_total
    update_total(db, ticket)
    record_event(db, ticket, "commerce.loyalty_reversed", ticket.status, line.performed_by_employee_id)
    db.commit()
    db.refresh(row)
    return row
