from decimal import Decimal, localcontext
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.payments.intents import persist_intent
from app.modules.payments.checkout import apply_capture
from app.modules.payments.provider import OperationKind, PaymentAmount
from app.modules.payments.models import PaymentIntent
from test_capture_checkout_9j import prepare
from test_payment_intents_9c import request
from test_ticket_workflow import _bootstrap_reference_data
from test_postgres_scheduling_4d import postgres_flow, race


def reserve(db, institute, ticket, key, amount, account="account", reference="reference"):
    return persist_intent(db, request(institute, ticket, idempotency_key=key,
        value=PaymentAmount(Decimal(amount), "CHF")), OperationKind.REFUND, "provider", account, reference)


def test_refund_budget_requires_applied_capture_and_reserves_exact_amounts(client):
    institute, employees, services = _bootstrap_reference_data(client)
    employee = employees[0]["id"]
    ticket, _, capture = prepare(main_module.engine, institute, employee, services[0]["id"])
    with Session(main_module.engine) as db, pytest.raises(HTTPException):
        reserve(db, institute, ticket, "before-application", "1")
    with Session(main_module.engine) as db:
        apply_capture(db, institute, capture, employee, "operator", "cb")
    for account, reference in (("other", "reference"), ("account", "foreign")):
        with Session(main_module.engine) as db, pytest.raises(HTTPException):
            reserve(db, institute, ticket, "wrong-parent", "1", account, reference)
    with Session(main_module.engine) as db:
        with localcontext() as context:
            context.prec = 2
            first = reserve(db, institute, ticket, "partial", "5.10").id
            reserve(db, institute, ticket, "remainder", "5.25")
            assert reserve(db, institute, ticket, "partial", "5.10").id == first
    with Session(main_module.engine) as db, pytest.raises(HTTPException, match="budget remboursable"):
        reserve(db, institute, ticket, "over-budget", "0.01")
    with Session(main_module.engine) as db:
        assert len(list(db.scalars(select(PaymentIntent).where(PaymentIntent.kind == "refund")))) == 2
    with Session(main_module.engine) as db, pytest.raises(HTTPException):
        reserve(db, institute, ticket, "partial", "5.11")


def test_concurrent_refund_reservations_cannot_overdraw_capture(postgres_flow):
    engine, institute, employee, care = postgres_flow
    ticket, _, capture = prepare(engine, institute, employee, care)
    with Session(engine) as db:
        apply_capture(db, institute, capture, employee, "operator", "cb")
    results = race(engine, [lambda db, key=key: reserve(db, institute, ticket, key, "6") for key in ("first", "second")])
    assert sum(row[0] == "ok" for row in results) == 1
    with Session(engine) as db:
        assert sum(db.scalars(select(PaymentIntent.amount).where(PaymentIntent.kind == "refund")), Decimal("0")) == Decimal("6.00")


def test_gift_funding_cannot_inflate_external_refund_budget(client):
    from app.modules.payments.executions import seal_authorization, seal_parent_operation
    from app.modules.payments.outcomes import record_authorization_outcome, record_parent_outcome
    from app.modules.payments.provider import ProviderResult, ProviderStatus
    from app.modules.gift_cards.service import issue_card
    from app.modules.gift_cards.tenders import allocate
    from app.modules.gift_cards.schemas import GiftCardIssue, AllocationCreate
    from test_loyalty_earning_8r import setup
    institute, employees, services = _bootstrap_reference_data(client)
    employee = employees[0]["id"]
    ticket, _, _ = setup(main_module.engine, institute, employee, services[0]["id"])
    with Session(main_module.engine) as db:
        card = issue_card(db, institute, GiftCardIssue(amount="20", valid_days=30, reason="Explicit credit", idempotency_key="gift"), "manager")
        allocate(db, institute, card.id, AllocationCreate(ticket_id=ticket, amount="1.35", idempotency_key="gift-payment"), "operator")
        value = PaymentAmount(Decimal("9.00"), "CHF")
        parent = persist_intent(db, request(institute, ticket, value=value), OperationKind.AUTHORIZE, "provider", "account").id
        seal_authorization(db, institute, parent)
        record_authorization_outcome(db, institute, parent, "provider", "account", ProviderResult("reference", ProviderStatus.AUTHORIZED, value))
        capture = persist_intent(db, request(institute, ticket, value=value, idempotency_key="capture"), OperationKind.CAPTURE, "provider", "account", "reference").id
        seal_parent_operation(db, institute, capture)
        record_parent_outcome(db, institute, capture, "provider", "account", ProviderResult("reference", ProviderStatus.CAPTURED, value))
        apply_capture(db, institute, capture, employee, "operator", "cb")
    with Session(main_module.engine) as db, pytest.raises(HTTPException):
        reserve(db, institute, ticket, "full-service-value", "10.35")
    with Session(main_module.engine) as db:
        reserve(db, institute, ticket, "external-only", "9.00")
