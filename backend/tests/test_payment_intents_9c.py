from decimal import Decimal
import pytest
from fastapi import HTTPException
from sqlalchemy import select, event
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.payments.models import PaymentIntent
from app.modules.payments.intents import persist_intent, original_request
from app.modules.payments.provider import PaymentAmount, PaymentRequest, OperationKind
from app.modules.tickets.models import QueueTicket
from app.shared.exceptions import business_error
from test_loyalty_earning_8r import setup
from test_ticket_workflow import _bootstrap_reference_data
from test_postgres_scheduling_4d import postgres_flow, race


def request(institute, ticket, **changes):
    terms = dict(institute_id=institute, ticket_id=ticket, value=PaymentAmount(Decimal("10.35"), "CHF"), idempotency_key="operation", actor_id="operator")
    return PaymentRequest(**{**terms, **changes})


def test_payment_intent_replay_scope_terms_and_rollback(client, monkeypatch):
    institute, employees, services = _bootstrap_reference_data(client)
    ticket, line, customer = setup(main_module.engine, institute, employees[0]["id"], services[0]["id"])
    intent = request(institute, ticket)
    def fail(db, context, instances):
        if any(isinstance(row, PaymentIntent) for row in db.new):
            raise business_error("Injected intent failure")
    event.listen(Session, "before_flush", fail)
    try:
        with Session(main_module.engine) as db, pytest.raises(HTTPException):
            persist_intent(db, intent, OperationKind.AUTHORIZE, "configured-provider", "account")
    finally:
        event.remove(Session, "before_flush", fail)
    with Session(main_module.engine) as db:
        assert list(db.scalars(select(PaymentIntent))) == []
        row = persist_intent(db, intent, OperationKind.AUTHORIZE, "configured-provider", "account")
        identifier = row.id
        assert original_request(row) == intent
        db.get(QueueTicket, ticket).total_amount = Decimal("99")
        db.commit()
        assert persist_intent(db, intent, OperationKind.AUTHORIZE, "configured-provider", "account").id == identifier
    for changed, provider, account in ((request(institute, ticket, actor_id="other"), "configured-provider", "account"),
        (request(institute, ticket, value=PaymentAmount(Decimal("11"), "CHF")), "configured-provider", "account"),
        (intent, "other-provider", "account"), (intent, "configured-provider", "other-account")):
        with Session(main_module.engine) as db, pytest.raises(HTTPException):
            persist_intent(db, changed, OperationKind.AUTHORIZE, provider, account)
    with Session(main_module.engine) as db, pytest.raises(HTTPException):
        persist_intent(db, request(institute, "missing", idempotency_key="missing"), OperationKind.AUTHORIZE, "configured-provider", "account")
    with Session(main_module.engine) as db, pytest.raises(HTTPException):
        persist_intent(db, request(institute, ticket, idempotency_key="currency", value=PaymentAmount(Decimal("1"), "EUR")), OperationKind.AUTHORIZE, "configured-provider", "account")
    with Session(main_module.engine) as db, pytest.raises(ValueError):
        persist_intent(db, intent, OperationKind.CAPTURE, "configured-provider", "account")
    assert client.post("/api/v1/dev/reset-demo", params={"institute_id": institute}).status_code == 400
    assert_downgrade_refused(main_module.engine, monkeypatch)


def test_duplicate_payment_intent_serializes(postgres_flow, monkeypatch):
    engine, institute, employee, care = postgres_flow
    ticket, line, customer = setup(engine, institute, employee, care)
    intent = request(institute, ticket)
    results = race(engine, [lambda db: persist_intent(db, intent, OperationKind.AUTHORIZE, "configured-provider", "account")] * 2)
    assert all(row[0] == "ok" for row in results) and results[0][1] == results[1][1]
    with Session(engine) as db:
        assert len(list(db.scalars(select(PaymentIntent)))) == 1

    assert_downgrade_refused(engine, monkeypatch)


def assert_downgrade_refused(engine, monkeypatch):
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
        command.stamp(config, "2cef6714379c")
        with pytest.raises(RuntimeError, match="cannot preserve"):
            command.downgrade(config, "1bde5603268b")
