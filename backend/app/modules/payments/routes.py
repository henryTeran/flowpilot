from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, StrictInt, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.permissions import require_ticket_manager
from app.database.session import get_db
from app.modules.payments.ledger import cashflow_snapshot

router = APIRouter(prefix="/payments/institutes/{institute_id}", tags=["payments"])


def operator(institute_id: str, user=Depends(require_ticket_manager)):
    actor = user.get("sub")
    if user.get("institute_id") != institute_id or not isinstance(actor, str) or not actor.strip() or actor != actor.strip() or len(actor) > 160:
        raise HTTPException(403, "Institut et identite de l'operatrice requis")
    return user


def manager(user=Depends(operator)):
    if user.get("role") != "responsable_institut":
        raise HTTPException(403, "Action reservee a la responsable")
    return user


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
def cashflows(institute_id: str, user=Depends(manager), db: Session = Depends(get_db)):
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
    idempotency_key: str
    points: int
    reason: str
    actor_id: str
    entry_id: str | None


@router.post("/refunds/{refund_id}/loyalty-decision", response_model=RefundLoyaltyRead)
def refund_loyalty(institute_id: str, refund_id: str, payload: RefundLoyaltyCreate,
                   user=Depends(manager), db: Session = Depends(get_db)):
    from app.modules.payments.refund_loyalty import decide_refund_loyalty
    return decide_refund_loyalty(db, institute_id, refund_id, payload.points, payload.reason, payload.idempotency_key, user["sub"])


@router.get("/refunds/{refund_id}/loyalty-decision", response_model=RefundLoyaltyRead | None)
def read_refund_loyalty(institute_id: str, refund_id: str, user=Depends(manager), db: Session = Depends(get_db)):
    from app.modules.payments.models import PaymentIntent, RefundLoyaltyDecision
    from app.modules.tickets.repository import lock_institute
    from app.shared.exceptions import not_found
    lock_institute(db, institute_id)
    intent = db.scalar(select(PaymentIntent).where(PaymentIntent.id == refund_id,
                      PaymentIntent.institute_id == institute_id, PaymentIntent.kind == "refund"))
    if intent is None:
        raise not_found("Remboursement introuvable")
    return db.scalar(select(RefundLoyaltyDecision).where(RefundLoyaltyDecision.institute_id == institute_id,
                                                        RefundLoyaltyDecision.refund_intent_id == refund_id))


class PaymentOperationRead(BaseModel):
    id: str
    kind: str
    amount: Decimal
    currency: str
    provider: str
    account_id: str
    idempotency_key: str
    actor_id: str
    status: str
    applied: bool
    active_protection: bool
    loyalty_decision: RefundLoyaltyRead | None


class TicketPaymentSnapshot(BaseModel):
    ticket_id: str
    protected: bool
    operations: list[PaymentOperationRead]


@router.get("/tickets/{ticket_id}/snapshot", response_model=TicketPaymentSnapshot)
def ticket_snapshot(institute_id: str, ticket_id: str, user=Depends(operator), db: Session = Depends(get_db)):
    from app.modules.payments.snapshots import ticket_payment_snapshot
    return ticket_payment_snapshot(db, institute_id, ticket_id)
