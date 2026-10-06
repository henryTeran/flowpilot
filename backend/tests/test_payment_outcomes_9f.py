from decimal import Decimal
import pytest
from fastapi import HTTPException
from sqlalchemy import select, event
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.payments.models import PaymentOutcome, PaymentExecution
from app.modules.payments.provider import ProviderResult, ProviderStatus, PaymentAmount, OperationKind
from app.modules.payments.intents import persist_intent
from app.modules.payments.executions import seal_authorization
from app.modules.payments.outcomes import record_authorization_outcome
from app.modules.tickets.service import attach_checkout_customer
from test_payment_intents_9c import request
from test_loyalty_earning_8r import setup
from test_ticket_workflow import _bootstrap_reference_data
from test_postgres_scheduling_4d import postgres_flow, race


def prepare(engine, institute, employee, care):
    ticket, _, _ = setup(engine, institute, employee, care)
    with Session(engine) as db:
        identifier = persist_intent(db, request(institute, ticket), OperationKind.AUTHORIZE, "provider", "account").id
        seal_authorization(db, institute, identifier)
    return ticket, identifier


def result(status, reference="reference", amount="10.35", currency="CHF"):
    return ProviderResult(reference, ProviderStatus(status), PaymentAmount(Decimal(amount), currency))


def record(db, institute, identifier, value):
    return record_authorization_outcome(db, institute, identifier, "provider", "account", value)


@pytest.mark.parametrize("terminal", ["authorized", "failed"])
def test_observation_replay_terminal_monotonicity_and_release(client, terminal, monkeypatch):
    institute, employees, services = _bootstrap_reference_data(client)
    ticket, identifier = prepare(main_module.engine, institute, employees[0]["id"], services[0]["id"])
    with Session(main_module.engine) as db:
        pending = record(db, institute, identifier, result("pending")).id
        assert db.get(PaymentExecution, identifier).released_at is None
        outcome = record(db, institute, identifier, result(terminal)).id
        assert record(db, institute, identifier, result(terminal)).id == outcome
        assert record(db, institute, identifier, result("pending")).id == pending
        assert (db.get(PaymentExecution, identifier).released_at is not None) == (terminal == "failed")
    with Session(main_module.engine) as db, pytest.raises(HTTPException):
        record(db, institute, identifier, result("failed" if terminal == "authorized" else "authorized"))
    with Session(main_module.engine) as db:
        if terminal == "failed":
            attach_checkout_customer(db, ticket, None)
        else:
            with pytest.raises(HTTPException):
                attach_checkout_customer(db, ticket, None)
    assert_downgrade_refused(main_module.engine, monkeypatch)


def test_observations_reject_wrong_scope_terms_reference_and_rollback(client):
    institute, employees, services = _bootstrap_reference_data(client)
    ticket, identifier = prepare(main_module.engine, institute, employees[0]["id"], services[0]["id"])
    with Session(main_module.engine) as db, pytest.raises(HTTPException):
        record(db, "foreign", identifier, result("authorized"))
    with Session(main_module.engine) as db, pytest.raises(HTTPException):
        record_authorization_outcome(db, institute, identifier, "provider", "other-account", result("authorized"))
    for invalid in (result("captured"), result("authorized", amount="11"), result("authorized", currency="EUR")):
        with Session(main_module.engine) as db, pytest.raises(ValueError):
            record(db, institute, identifier, invalid)
    def fail(db, context, instances):
        if any(isinstance(row, PaymentOutcome) for row in db.new):
            raise RuntimeError("Injected outcome write failure")
    event.listen(Session, "before_flush", fail)
    try:
        with Session(main_module.engine) as db, pytest.raises(RuntimeError):
            record(db, institute, identifier, result("failed"))
    finally:
        event.remove(Session, "before_flush", fail)
    with Session(main_module.engine) as db:
        assert list(db.scalars(select(PaymentOutcome))) == []
        assert db.get(PaymentExecution, identifier).released_at is None
        record(db, institute, identifier, result("pending"))
    with Session(main_module.engine) as db, pytest.raises(HTTPException):
        record(db, institute, identifier, result("authorized", reference="different"))
    with Session(main_module.engine) as db:
        record(db, institute, identifier, result("failed"))
        other = persist_intent(db, request(institute, ticket, idempotency_key="other-attempt"), OperationKind.AUTHORIZE, "provider", "account").id
        seal_authorization(db, institute, other)
    with Session(main_module.engine) as db, pytest.raises(HTTPException):
        record(db, institute, other, result("authorized"))


def test_duplicate_results_serialize(postgres_flow, monkeypatch):
    engine, institute, employee, care = postgres_flow
    _, identifier = prepare(engine, institute, employee, care)
    results = race(engine, [lambda db: record(db, institute, identifier, result("failed"))] * 2)
    assert all(row[0] == "ok" for row in results) and results[0][1] == results[1][1]
    with Session(engine) as db:
        assert len(list(db.scalars(select(PaymentOutcome)))) == 1
        assert db.get(PaymentExecution, identifier).released_at is not None
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
        command.stamp(config, "4eab893659be")
        with pytest.raises(RuntimeError, match="cannot preserve provider facts"):
            command.downgrade(config, "3dfa782548ad")


def test_provider_result_requires_prior_durable_execution(client):
    institute, employees, services = _bootstrap_reference_data(client)
    ticket, _, _ = setup(main_module.engine, institute, employees[0]["id"], services[0]["id"])
    with Session(main_module.engine) as db:
        identifier = persist_intent(db, request(institute, ticket), OperationKind.AUTHORIZE, "provider", "account").id
        with pytest.raises(HTTPException, match="Execution durable"):
            record(db, institute, identifier, result("authorized"))
