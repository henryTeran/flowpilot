"""Award once with paid checkout, using explicit immutable policy and invoice facts."""
from decimal import Decimal, ROUND_FLOOR
from sqlalchemy import select
from app.modules.customers.models import Customer
from app.modules.gift_cards.service import require_settings
from app.modules.loyalty.models import LoyaltyEntry, LoyaltyEarning, LoyaltyEarningPolicy
from app.modules.loyalty.service import points
from app.modules.tickets.models import TicketLine
from app.modules.tickets.repository import lock_institute
from app.shared.exceptions import business_error
from app.shared.ids import new_id
from app.shared.time import utcnow


def current_policy(db, institute):
    return db.scalar(select(LoyaltyEarningPolicy).where(LoyaltyEarningPolicy.institute_id == institute)
                     .order_by(LoyaltyEarningPolicy.revision.desc()).limit(1))


def create_policy(db, institute, payload, actor):
    lock_institute(db, institute)
    old = db.scalar(select(LoyaltyEarningPolicy).where(LoyaltyEarningPolicy.institute_id == institute,
                                              LoyaltyEarningPolicy.idempotency_key == payload.idempotency_key))
    if old:
        if any(getattr(old, field) != getattr(payload, field) for field in ("currency", "points_per_unit", "enabled", "reason")):
            raise business_error("Cette cle appartient a une autre politique de fidelite")
        return old
    settings = require_settings(db, institute)
    db.refresh(settings)
    if settings.currency != payload.currency:
        raise business_error("La politique doit utiliser la devise configuree de l'institut")
    last = current_policy(db, institute)
    row = LoyaltyEarningPolicy(id=new_id("lep"), institute_id=institute, revision=last.revision + 1 if last else 1,
        actor_id=actor, created_at=utcnow(), **payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def award_checkout(db, ticket, actor, operator_institute):
    # The checkout caller holds the institute lock and commits all facts together.
    policy = current_policy(db, ticket.institute_id)
    if policy is None or not policy.enabled or not ticket.customer_id:
        return
    customer = db.get(Customer, ticket.customer_id)
    if customer is None or customer.institute_id != ticket.institute_id:
        return  # Keep anonymous and opaque legacy identities outside loyalty.
    if operator_institute != ticket.institute_id:
        raise business_error("Institut de l'operatrice requis pour l'acquisition de points")
    if ticket.status != "paid" or ticket.currency != policy.currency:
        raise business_error("Devise du ticket confirmee requise pour l'acquisition de points")
    if not isinstance(actor, str) or not actor.strip() or len(actor) > 160:
        raise business_error("Identite signee requise pour l'acquisition de points")
    if db.get(LoyaltyEarning, ticket.id) is not None:
        return
    db.flush()
    basis = sum((Decimal(str(line.total or 0)) for line in db.scalars(select(TicketLine).where(TicketLine.invoice_removed_at.is_(None)).where(
        TicketLine.ticket_id == ticket.id))), Decimal("0"))
    if not basis.is_finite() or basis < 0:
        raise business_error("Montant du ticket invalide pour la fidelite")
    awarded = int((basis * policy.points_per_unit).to_integral_value(rounding=ROUND_FLOOR))
    if points(db, ticket.institute_id, customer.id) + awarded > 1_000_000_000_000:
        raise business_error("Limite du solde de points depassee")
    entry_id = None
    if awarded:
        entry_id = new_id("lp")
        db.add(LoyaltyEntry(id=entry_id, institute_id=ticket.institute_id, customer_id=customer.id,
            points=awarded, reason="Acquisition sur ticket cloture", actor_id=actor, occurred_at=ticket.paid_at,
            idempotency_key=f"checkout:{entry_id}"))
        db.flush()
    db.add(LoyaltyEarning(ticket_id=ticket.id, institute_id=ticket.institute_id, customer_id=customer.id,
        policy_id=policy.id, entry_id=entry_id, currency=policy.currency, basis_amount=basis,
        points_per_unit=policy.points_per_unit, points=awarded, actor_id=actor, occurred_at=ticket.paid_at))
