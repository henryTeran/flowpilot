from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.core.permissions import require_ticket_manager
from app.modules.customers.repository import require_customer
from app.modules.loyalty import service
from app.modules.loyalty.models import LoyaltyEntry, LoyaltyTier
from app.modules.loyalty.schemas import AdjustmentCreate, BalanceRead, EntryRead, TierCreate, TierRead
from app.modules.tickets.repository import lock_institute

router = APIRouter(prefix="/loyalty/institutes/{institute_id}", tags=["loyalty"])


def operator(institute_id: str, user=Depends(require_ticket_manager)):
    actor = user.get("sub")
    if user.get("institute_id") != institute_id or not isinstance(actor, str) or not actor.strip() or len(actor) > 160:
        raise HTTPException(403, "Institut et identite de l'operatrice requis")
    return user


def manager(user=Depends(operator)):
    if user["role"] != "responsable_institut":
        raise HTTPException(403, "Correction et niveaux reserves a la responsable")
    return user


@router.get("/tiers", response_model=list[TierRead])
def tiers(institute_id: str, user=Depends(operator), db: Session = Depends(get_db)):
    return list(db.scalars(select(LoyaltyTier).where(LoyaltyTier.institute_id == institute_id).order_by(LoyaltyTier.minimum_points)))


@router.post("/tiers", response_model=TierRead)
def create_tier(institute_id: str, payload: TierCreate, user=Depends(manager), db: Session = Depends(get_db)):
    return service.create_tier(db, institute_id, payload, user["sub"])


@router.get("/customers/{customer_id}", response_model=BalanceRead)
def balance(institute_id: str, customer_id: str, user=Depends(operator), db: Session = Depends(get_db)):
    lock_institute(db, institute_id)
    return service.balance(db, institute_id, customer_id)


@router.get("/customers/{customer_id}/history", response_model=list[EntryRead])
def history(institute_id: str, customer_id: str, user=Depends(operator), db: Session = Depends(get_db)):
    require_customer(db, institute_id, customer_id)
    return list(db.scalars(select(LoyaltyEntry).where(LoyaltyEntry.institute_id == institute_id,
        LoyaltyEntry.customer_id == customer_id).order_by(LoyaltyEntry.occurred_at, LoyaltyEntry.id)))


@router.post("/customers/{customer_id}/adjustments", response_model=EntryRead)
def adjust(institute_id: str, customer_id: str, payload: AdjustmentCreate, user=Depends(manager), db: Session = Depends(get_db)):
    return service.adjust(db, institute_id, customer_id, payload, user["sub"])
