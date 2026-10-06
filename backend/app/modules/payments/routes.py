from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
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
