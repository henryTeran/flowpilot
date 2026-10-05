from sqlalchemy import func, select
from app.modules.customers.repository import require_customer
from app.modules.loyalty.models import LoyaltyEntry, LoyaltyTier
from app.modules.tickets.repository import lock_institute
from app.shared.exceptions import business_error
from app.shared.ids import new_id
from app.shared.time import utcnow


def points(db, institute, customer):
    return int(db.scalar(select(func.coalesce(func.sum(LoyaltyEntry.points), 0)).where(
        LoyaltyEntry.institute_id == institute, LoyaltyEntry.customer_id == customer)))


def balance(db, institute, customer):
    require_customer(db, institute, customer)
    amount = points(db, institute, customer)
    tier = db.scalar(select(LoyaltyTier).where(LoyaltyTier.institute_id == institute,
        LoyaltyTier.minimum_points <= amount).order_by(LoyaltyTier.minimum_points.desc()))
    return dict(customer_id=customer, points=amount, tier=tier)


def adjust(db, institute, customer, payload, actor):
    lock_institute(db, institute)
    require_customer(db, institute, customer)
    old = db.scalar(select(LoyaltyEntry).where(LoyaltyEntry.institute_id == institute,
                                               LoyaltyEntry.idempotency_key == payload.idempotency_key))
    if old:
        if (old.customer_id, old.points, old.reason) != (customer, payload.points, payload.reason):
            raise business_error("Cette cle appartient a une autre correction de points")
        return old
    if payload.points == 0:
        raise business_error("La correction doit modifier les points")
    new_balance = points(db, institute, customer) + payload.points
    if new_balance < 0 or new_balance > 1_000_000_000_000:
        raise business_error("Le solde de points doit rester positif ou nul et dans la limite autorisee")
    row = LoyaltyEntry(id=new_id("lp"), institute_id=institute, customer_id=customer,
        actor_id=actor, occurred_at=utcnow(), **payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def create_tier(db, institute, payload, actor):
    lock_institute(db, institute)
    old = db.scalar(select(LoyaltyTier).where(LoyaltyTier.institute_id == institute,
                                              LoyaltyTier.idempotency_key == payload.idempotency_key))
    if old:
        if (old.name, old.minimum_points, old.benefit_description) != (payload.name, payload.minimum_points, payload.benefit_description):
            raise business_error("Cette cle appartient a un autre niveau de fidelite")
        return old
    if db.scalar(select(LoyaltyTier.id).where(LoyaltyTier.institute_id == institute,
                                             LoyaltyTier.minimum_points == payload.minimum_points)):
        raise business_error("Un niveau utilise deja ce seuil de points")
    row = LoyaltyTier(id=new_id("lt"), institute_id=institute, actor_id=actor, created_at=utcnow(), **payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def create_reward(db, institute, payload, actor):
    from app.modules.loyalty.models import LoyaltyReward
    from app.modules.gift_cards.service import require_settings
    from app.modules.services.repository import get_service
    lock_institute(db, institute)
    old = db.scalar(select(LoyaltyReward).where(LoyaltyReward.institute_id == institute,
                                              LoyaltyReward.idempotency_key == payload.idempotency_key))
    if old:
        if any(getattr(old, field) != value for field, value in payload.model_dump().items()):
            raise business_error("Cette cle appartient a une autre recompense")
        return old
    settings = require_settings(db, institute)
    db.refresh(settings)
    if settings.currency != payload.currency:
        raise business_error("La recompense doit utiliser la devise configuree")
    if get_service(db, payload.service_id) is None:
        raise business_error("Prestation declaree requise pour la recompense")
    row = LoyaltyReward(id=new_id("lr"), institute_id=institute,
                        actor_id=actor, created_at=utcnow(), **payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
