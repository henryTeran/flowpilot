import pytest
from fastapi import HTTPException
from sqlalchemy import event, select
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.payments.checkout import apply_capture
from app.modules.payments.models import CaptureApplication, PaymentExecution
from app.modules.payments.outcomes import record_parent_outcome
from app.modules.payments.executions import seal_parent_operation
from app.modules.payments.provider import OperationKind
from app.modules.tickets.models import QueueTicket
from app.modules.loyalty.models import LoyaltyEarning
from app.modules.loyalty.earning import create_policy
from app.modules.loyalty.schemas import EarningPolicyCreate
from test_payment_parent_execution_9i import child
from test_payment_outcomes_9f import result
from test_ticket_workflow import _bootstrap_reference_data
from test_postgres_scheduling_4d import postgres_flow, race


def prepare(engine, institute, employee, care):
    ticket, parent, identifier, _ = child(engine, institute, employee, care, OperationKind.CAPTURE)
    with Session(engine) as db:
        create_policy(db, institute, EarningPolicyCreate(currency="CHF", points_per_unit="1", enabled=True, reason="Explicit policy", idempotency_key="earning"), "manager")
        seal_parent_operation(db, institute, identifier)
        record_parent_outcome(db, institute, identifier, "provider", "account", result("captured"))
    return ticket, parent, identifier


def test_captured_checkout_atomic_earning_replay_and_scope(client, monkeypatch):
    institute, employees, services = _bootstrap_reference_data(client)
    employee = employees[0]["id"]
    ticket, parent, identifier = prepare(main_module.engine, institute, employee, services[0]["id"])
    with Session(main_module.engine) as db, pytest.raises(HTTPException):
        apply_capture(db, "foreign", identifier, employee, "operator", "cb")
    with Session(main_module.engine) as db:
        assert apply_capture(db, institute, identifier, employee, "operator", "cb").status == "paid"
        assert apply_capture(db, institute, identifier, employee, "operator", "cb").id == ticket
        assert db.get(PaymentExecution, parent).released_at is not None
        assert db.get(LoyaltyEarning, ticket).points == 10
        with pytest.raises(HTTPException):
            apply_capture(db, institute, identifier, employee, "operator", "especes")

    assert_application_downgrade_refused(main_module.engine, monkeypatch)

def test_failed_earning_rolls_back_application_release_and_paid_ticket(client):
    institute, employees, services = _bootstrap_reference_data(client)
    employee = employees[0]["id"]
    ticket, parent, identifier = prepare(main_module.engine, institute, employee, services[0]["id"])
    def fail(db, context, instances):
        if any(isinstance(row, LoyaltyEarning) for row in db.new):
            raise RuntimeError("Injected earning failure")
    event.listen(Session, "before_flush", fail)
    try:
        with Session(main_module.engine) as db, pytest.raises(RuntimeError):
            apply_capture(db, institute, identifier, employee, "operator", "cb")
    finally:
        event.remove(Session, "before_flush", fail)
    with Session(main_module.engine) as db:
        assert db.get(CaptureApplication, ticket) is None
        assert db.get(PaymentExecution, parent).released_at is None
        assert db.get(QueueTicket, ticket).status == "ready_for_checkout"
        assert db.get(LoyaltyEarning, ticket) is None
        apply_capture(db, institute, identifier, employee, "operator", "cb")


def test_duplicate_capture_application_serializes(postgres_flow, monkeypatch):
    engine, institute, employee, care = postgres_flow
    ticket, parent, identifier = prepare(engine, institute, employee, care)
    results = race(engine, [lambda db: apply_capture(db, institute, identifier, employee, "operator", "cb")] * 2)
    assert all(row[0] == "ok" for row in results) and results[0][1] == results[1][1]
    with Session(engine) as db:
        assert len(list(db.scalars(select(CaptureApplication)))) == 1
        assert db.get(LoyaltyEarning, ticket).points == 10

    assert_application_downgrade_refused(engine, monkeypatch)

def test_mixed_capture_applies_only_external_remainder(client):
    from decimal import Decimal, localcontext
    from app.modules.payments.intents import persist_intent
    from app.modules.payments.executions import seal_authorization
    from app.modules.payments.outcomes import record_authorization_outcome
    from app.modules.payments.provider import PaymentAmount, ProviderResult, ProviderStatus
    from app.modules.gift_cards.service import issue_card
    from app.modules.gift_cards.tenders import allocate
    from app.modules.gift_cards.schemas import GiftCardIssue, AllocationCreate
    from app.modules.gift_cards.models import GiftTenderClosure
    from test_loyalty_earning_8r import setup
    from test_payment_intents_9c import request
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
        with localcontext() as context:
            context.prec = 2
            assert apply_capture(db, institute, capture, employee, "operator", "cb").payment_method == "mixte"
        closure = db.get(GiftTenderClosure, ticket)
        assert closure.gift_amount == Decimal("1.35") and closure.remainder_amount == Decimal("9.00")
        assert closure.remainder_method == "cb"


def assert_application_downgrade_refused(engine, monkeypatch):
    from pathlib import Path
    from alembic import command
    from alembic.config import Config
    from app.core.config import settings
    from sqlalchemy import text
    url = engine.url
    if engine.dialect.name == "postgresql":
        with engine.connect() as connection:
            schema = connection.scalar(text("SELECT current_schema()"))
        assert schema.startswith("fp_test_")
        url = url.update_query_dict({"options": f"-csearch_path={schema}"})
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
    with monkeypatch.context() as patch:
        patch.setattr(settings, "DATABASE_URL", url.render_as_string(hide_password=False))
        command.stamp(config, "60cd01587bdf")
        with pytest.raises(RuntimeError, match="cannot preserve settlement application"):
            command.downgrade(config, "5fbc90476acf")
