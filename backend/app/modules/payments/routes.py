from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, StrictInt, Field
from sqlalchemy.orm import Session
from app.core.permissions import require_ticket_manager
from app.database.session import get_db
from app.modules.payments.ledger import cashflow_snapshot

router = APIRouter(prefix="/payments/institutes/{institute_id}", tags=["payments"])


class AccountCashflow(BaseModel):
    provider: str
    account_id: str
    currency: str
    captured: Decimal
    applied: Decimal
    unapplied: Decimal
    refunded: Decimal
    refund_reserved: Decimal
    net_confirmed: Decimal


class CashflowSnapshot(BaseModel):
    institute_id: str
    accounts: list[AccountCashflow]


@router.get("/cashflows", response_model=CashflowSnapshot)
def cashflows(institute_id: str, user=Depends(require_ticket_manager), db: Session = Depends(get_db)):
    actor = user.get("sub")
    if user.get("role") != "responsable_institut" or user.get("institute_id") != institute_id or not isinstance(actor, str) or not actor.strip() or len(actor) > 160:
        raise HTTPException(403, "Institut et identite de la responsable requis")
    return cashflow_snapshot(db, institute_id)


class RefundLoyaltyCreate(BaseModel):
    model_config = {"extra": "forbid"}
    points: StrictInt = Field(ge=-1_000_000_000, le=0)
    reason: str = Field(min_length=1, max_length=240, pattern=r"^\S(?:[\s\S]*\S)?$")
    idempotency_key: str = Field(min_length=1, max_length=120, pattern=r"^\S(?:[\s\S]*\S)?$")


class RefundLoyaltyRead(BaseModel):
    model_config = {"from_attributes": True}
    id: str
    refund_intent_id: str
    points: int
    reason: str
    actor_id: str
    entry_id: str | None


@router.post("/refunds/{refund_id}/loyalty-decision", response_model=RefundLoyaltyRead)
def refund_loyalty(institute_id: str, refund_id: str, payload: RefundLoyaltyCreate,
                   user=Depends(require_ticket_manager), db: Session = Depends(get_db)):
    from app.modules.payments.refund_loyalty import decide_refund_loyalty
    actor = user.get("sub")
    if user.get("role") != "responsable_institut" or user.get("institute_id") != institute_id or not isinstance(actor, str) or not actor.strip() or actor != actor.strip() or len(actor) > 160:
        raise HTTPException(403, "Institut et identite de la responsable requis")
    return decide_refund_loyalty(db, institute_id, refund_id, payload.points, payload.reason, payload.idempotency_key, actor)
