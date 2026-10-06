from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, StrictInt, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.permissions import require_ticket_manager
from app.database.session import get_db
from app.modules.payments.ledger import cashflow_snapshot
from app.modules.payments.provider import OperationKind
from app.modules.payments.registry import configured_binding, payment_sessions
from typing import Literal

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


class PaymentPrepare(BaseModel):
    model_config = {"extra": "forbid"}
    kind: OperationKind
    amount: Decimal = Field(gt=0, le=Decimal("99999999.99"), decimal_places=2)
    currency: Literal["CHF", "EUR"]
    idempotency_key: str = Field(min_length=1, max_length=120, strict=True)
    parent_intent_id: str | None = Field(default=None, min_length=1, max_length=80, strict=True)


class PaymentPrepared(BaseModel):
    model_config = {"from_attributes": True}
    id: str
    kind: str
    amount: Decimal
    currency: str
    idempotency_key: str


class AuthorizationQuoteRead(BaseModel):
    ticket_id: str
    amount: Decimal
    currency: Literal["CHF", "EUR"]


@router.get("/tickets/{ticket_id}/authorization-quote", response_model=AuthorizationQuoteRead)
def authorization_quote(institute_id: str, ticket_id: str, user=Depends(operator),
                        binding=Depends(configured_binding), db: Session = Depends(get_db)):
    from app.modules.tickets.repository import lock_institute
    from app.modules.tickets.models import QueueTicket
    from app.modules.payments.quotes import authorization_amount
    from app.shared.exceptions import not_found
    lock_institute(db, institute_id)
    ticket = db.scalar(select(QueueTicket).where(QueueTicket.id == ticket_id, QueueTicket.institute_id == institute_id)
                       .execution_options(populate_existing=True))
    if ticket is None:
        raise not_found("Ticket de paiement introuvable")
    value = authorization_amount(db, ticket)
    return dict(ticket_id=ticket.id, amount=value.amount, currency=value.currency)


class PaymentDispatched(BaseModel):
    id: str
    kind: str
    status: str
    amount: Decimal
    currency: str


@router.post("/tickets/{ticket_id}/intents", response_model=PaymentPrepared)
def prepare_payment(institute_id: str, ticket_id: str, payload: PaymentPrepare, user=Depends(operator),
                    binding=Depends(configured_binding), db: Session = Depends(get_db)):
    from app.modules.payments.operator_service import prepare
    return prepare(db, institute_id, ticket_id, payload, user, binding)


@router.post("/intents/{intent_id}/dispatch", response_model=PaymentDispatched)
def dispatch_payment(institute_id: str, intent_id: str, user=Depends(operator),
                     binding=Depends(configured_binding), sessions=Depends(payment_sessions)):
    from app.modules.payments.operator_service import dispatch
    return dispatch(sessions, institute_id, intent_id, user, binding)


class CaptureCheckoutCreate(BaseModel):
    model_config = {"extra": "forbid"}
    employee_id: str = Field(min_length=1, max_length=80, strict=True)
    method: Literal["cb", "especes", "cheque"]


class CaptureCheckoutRead(BaseModel):
    ticket_id: str
    status: str


@router.post("/intents/{intent_id}/checkout", response_model=CaptureCheckoutRead)
def captured_checkout(institute_id: str, intent_id: str, payload: CaptureCheckoutCreate,
                      user=Depends(operator), db: Session = Depends(get_db)):
    from app.modules.payments.checkout import apply_capture
    ticket = apply_capture(db, institute_id, intent_id, payload.employee_id, user["sub"], payload.method)
    return dict(ticket_id=ticket.id, status=ticket.status)


class WebhookAcknowledgement(BaseModel):
    received: bool


@router.post("/webhook", response_model=WebhookAcknowledgement)
async def payment_webhook(institute_id: str, request: Request,
                          binding=Depends(configured_binding), sessions=Depends(payment_sessions)):
    from starlette.concurrency import run_in_threadpool
    from app.modules.payments.provider import RawWebhook
    from app.modules.payments.webhooks import receive_webhook
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > 65_536:
            raise HTTPException(413, "Notification de paiement trop volumineuse")
        body.extend(chunk)
    event = RawWebhook(bytes(body), dict(request.headers))
    try:
        await run_in_threadpool(receive_webhook, sessions, binding, event)
    except HTTPException:
        raise
    except (ValueError, PermissionError) as failure:
        raise HTTPException(400, "Notification de paiement non valide") from failure
    except Exception as failure:
        raise HTTPException(503, "Notification a retransmettre sans modifier son identite") from failure
    return dict(received=True)


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
