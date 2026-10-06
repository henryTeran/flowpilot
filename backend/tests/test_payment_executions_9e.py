import pytest
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import select, event
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.payments.models import PaymentExecution, PaymentIntent
from app.modules.payments.intents import persist_intent
from app.modules.payments.executions import seal_authorization
from app.modules.payments.provider import OperationKind
from app.modules.tickets.models import TicketLine
from app.modules.tickets.service import attach_checkout_customer, complete_payment, add_checkout_ticket_line, cancel_ticket
from app.modules.gift_cards.tenders import require_no_active_tender
from test_payment_intents_9c import request
from test_loyalty_earning_8r import setup
from test_ticket_workflow import _bootstrap_reference_data
from test_postgres_scheduling_4d import postgres_flow, race


def test_seal_durable_replay_scope_and_checkout_mutations(client, monkeypatch):
    institute, employees, services = _bootstrap_reference_data(client)
    employee, care = employees[0]["id"], services[0]["id"]
    ticket, line, customer = setup(main_module.engine, institute, employee, care)
    intent = request(institute, ticket)
    with Session(main_module.engine) as db:
        row = persist_intent(db, intent, OperationKind.AUTHORIZE, "provider", "account")
        identifier = row.id
        other = persist_intent(db, request(institute, ticket, idempotency_key="other"), OperationKind.AUTHORIZE, "provider", "account").id
        assert seal_authorization(db, institute, identifier) == intent
    with Session(main_module.engine) as db:
        assert db.get(PaymentExecution, identifier).released_at is None
        with pytest.raises(HTTPException):
            seal_authorization(db, institute, other)
        db.rollback()
        with pytest.raises(HTTPException):
            seal_authorization(db, "foreign", identifier)
    for action in (
        lambda db: attach_checkout_customer(db, ticket, None),
        lambda db: complete_payment(db, ticket, employee, "cb"),
        lambda db: add_checkout_ticket_line(db, ticket, care),
        lambda db: cancel_ticket(db, ticket),
    ):
        with Session(main_module.engine) as db, pytest.raises(HTTPException, match="Paiement prestataire"):
            action(db)
    with Session(main_module.engine) as db:
        from app.modules.tickets.models import QueueTicket
        with pytest.raises(HTTPException):
            require_no_active_tender(db, db.get(QueueTicket, ticket))
        db.rollback()
        # Recovery cannot be turned into a fresh quote, even if external corruption occurs.
        db.get(TicketLine, line).unit_price = Decimal("11")
        db.get(TicketLine, line).total = Decimal("11")
        db.commit()
        assert seal_authorization(db, institute, identifier) == intent
    assert_seal_downgrade_refused(main_module.engine, monkeypatch)


def test_failed_seal_write_leaves_no_execution(client):
    institute, employees, services = _bootstrap_reference_data(client)
    ticket, _, _ = setup(main_module.engine, institute, employees[0]["id"], services[0]["id"])
    with Session(main_module.engine) as db:
        identifier = persist_intent(db, request(institute, ticket), OperationKind.AUTHORIZE, "provider", "account").id
    def fail(db, context, instances):
        if any(isinstance(row, PaymentExecution) for row in db.new):
            raise RuntimeError("Injected seal write failure")
    event.listen(Session, "before_flush", fail)
    try:
        with Session(main_module.engine) as db, pytest.raises(RuntimeError):
            seal_authorization(db, institute, identifier)
    finally:
        event.remove(Session, "before_flush", fail)
    with Session(main_module.engine) as db:
        assert list(db.scalars(select(PaymentExecution))) == []
        seal_authorization(db, institute, identifier)


def test_competing_authorizations_have_one_durable_seal(postgres_flow, monkeypatch):
    engine, institute, employee, care = postgres_flow
    ticket, _, _ = setup(engine, institute, employee, care)
    with Session(engine) as db:
        identifiers = [persist_intent(db, request(institute, ticket, idempotency_key=key), OperationKind.AUTHORIZE, "provider", "account").id for key in ("a", "b")]
    def seal(db, identifier):
        seal_authorization(db, institute, identifier)
        return db.get(PaymentIntent, identifier)
    results = race(engine, [lambda db, identifier=identifier: seal(db, identifier) for identifier in identifiers])
    assert sum(result[0] == "ok" for result in results) == 1
    with Session(engine) as db:
        assert len(list(db.scalars(select(PaymentExecution)))) == 1
    assert_seal_downgrade_refused(engine, monkeypatch)


def assert_seal_downgrade_refused(engine, monkeypatch):
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
        command.stamp(config, "3dfa782548ad")
        with pytest.raises(RuntimeError, match="cannot preserve execution seals"):
            command.downgrade(config, "2cef6714379c")


def test_price_mutation_and_seal_serialize(postgres_flow):
    engine, institute, employee, care = postgres_flow
    ticket, _, _ = setup(engine, institute, employee, care)
    with Session(engine) as db:
        identifier = persist_intent(db, request(institute, ticket), OperationKind.AUTHORIZE, "provider", "account").id
    def seal(db):
        seal_authorization(db, institute, identifier)
        return db.get(PaymentIntent, identifier)
    results = race(engine, [seal, lambda db: add_checkout_ticket_line(db, ticket, care)])
    assert sum(result[0] == "ok" for result in results) == 1
    with Session(engine) as db:
        lines = list(db.scalars(select(TicketLine).where(TicketLine.ticket_id == ticket)))
        sealed = db.get(PaymentExecution, identifier)
        assert (sealed is not None and len(lines) == 1) or (sealed is None and len(lines) == 2)


def test_seal_blocks_new_gift_funding_and_reversal_but_keeps_allocation_replay(client):
    from app.modules.gift_cards.service import issue_card
    from app.modules.gift_cards.schemas import GiftCardIssue, AllocationCreate
    from app.modules.gift_cards.tenders import allocate, reverse
    from app.modules.payments.provider import PaymentAmount
    institute, employees, services = _bootstrap_reference_data(client)
    ticket, _, _ = setup(main_module.engine, institute, employees[0]["id"], services[0]["id"])
    with Session(main_module.engine) as db:
        card = issue_card(db, institute, GiftCardIssue(amount="20", valid_days=30, reason="Explicit credit", idempotency_key="gift"), "manager")
        payload = AllocationCreate(ticket_id=ticket, amount="1.35", idempotency_key="funding")
        allocation = allocate(db, institute, card.id, payload, "operator")
        card_id, allocation_id = card.id, allocation.id
        row = persist_intent(db, request(institute, ticket, value=PaymentAmount(Decimal("9.00"), "CHF")), OperationKind.AUTHORIZE, "provider", "account")
        seal_authorization(db, institute, row.id)
        assert allocate(db, institute, card_id, payload, "operator").id == allocation_id
    with Session(main_module.engine) as db, pytest.raises(HTTPException, match="Paiement prestataire"):
        allocate(db, institute, card_id, AllocationCreate(ticket_id=ticket, amount="1", idempotency_key="new-funding"), "operator")
    with Session(main_module.engine) as db, pytest.raises(HTTPException, match="Paiement prestataire"):
        reverse(db, institute, allocation_id, "Correction", "manager")
