import pytest
from sqlalchemy import select, event
from sqlalchemy.orm import Session
from fastapi import HTTPException
import app.main as main_module
from app.modules.payments.refund_loyalty import decide_refund_loyalty
from app.modules.payments.refunds import seal_refund, record_refund_outcome
from app.modules.payments.models import RefundLoyaltyDecision
from app.modules.loyalty.service import points
from app.modules.payments.provider import ProviderResult, ProviderStatus
from test_refund_execution_9l import prepared
from test_ticket_workflow import _bootstrap_reference_data, _auth_headers
from test_postgres_scheduling_4d import postgres_flow, race


def refunded(engine, institute, employee, care):
    ticket, refund = prepared(engine, institute, employee, care)
    with Session(engine) as db:
        request = seal_refund(db, institute, refund)
        record_refund_outcome(db, institute, refund, "provider", "account", ProviderResult("reference", ProviderStatus.REFUNDED, request.value))
    return ticket, refund


def test_signed_refund_loyalty_scope_replay_and_bounds(client, monkeypatch):
    institute, employees, services = _bootstrap_reference_data(client)
    ticket, refund = refunded(main_module.engine, institute, employees[0]["id"], services[0]["id"])
    path = f"/api/v1/payments/institutes/{institute}/refunds/{refund}/loyalty-decision"
    payload = dict(points=-5, reason="Declared refund correction", idempotency_key="decision")
    for headers in (_auth_headers(institute_id=institute), _auth_headers("responsable_institut", "foreign")):
        assert client.post(path, headers=headers, json=payload).status_code == 403
    manager = _auth_headers("responsable_institut", institute)
    for invalid in (True, 1, -11):
        assert client.post(path, headers=manager, json={**payload, "points": invalid}).status_code in {400, 422}
    first = client.post(path, headers=manager, json=payload)
    assert first.status_code == 200
    assert client.post(path, headers=manager, json=payload).json() == first.json()
    assert client.post(path, headers=manager, json={**payload, "idempotency_key": "other"}).status_code == 400
    with Session(main_module.engine) as db:
        fact = db.get(RefundLoyaltyDecision, first.json()["id"])
        assert points(db, institute, fact.customer_id) == 5

    assert_decision_downgrade_refused(main_module.engine, monkeypatch)

def test_decision_failure_rolls_back_points_and_preserve_is_explicit(client):
    institute, employees, services = _bootstrap_reference_data(client)
    _, refund = refunded(main_module.engine, institute, employees[0]["id"], services[0]["id"])
    def fail(db, context, instances):
        if any(isinstance(row, RefundLoyaltyDecision) for row in db.new):
            raise RuntimeError("Injected decision failure")
    event.listen(Session, "before_flush", fail)
    try:
        with Session(main_module.engine) as db, pytest.raises(RuntimeError):
            decide_refund_loyalty(db, institute, refund, -5, "Explicit correction", "decision", "manager")
    finally:
        event.remove(Session, "before_flush", fail)
    with Session(main_module.engine) as db:
        assert list(db.scalars(select(RefundLoyaltyDecision))) == []
        fact = decide_refund_loyalty(db, institute, refund, 0, "Points explicitly retained", "preserve", "manager")
        assert fact.entry_id is None and points(db, institute, fact.customer_id) == 10


def test_duplicate_refund_decisions_serialize(postgres_flow, monkeypatch):
    engine, institute, employee, care = postgres_flow
    _, refund = refunded(engine, institute, employee, care)
    results = race(engine, [lambda db: decide_refund_loyalty(db, institute, refund, -5, "Explicit correction", "decision", "manager")] * 2)
    assert all(row[0] == "ok" for row in results) and results[0][1] == results[1][1]
    with Session(engine) as db:
        facts = list(db.scalars(select(RefundLoyaltyDecision)))
        assert len(facts) == 1 and points(db, institute, facts[0].customer_id) == 5

    assert_decision_downgrade_refused(engine, monkeypatch)

def test_partial_refund_decisions_cannot_deduct_more_than_original_earning(client):
    from test_capture_checkout_9j import prepare
    from test_refund_budget_9k import reserve
    from app.modules.payments.checkout import apply_capture
    from app.modules.loyalty.service import adjust
    from app.modules.loyalty.schemas import AdjustmentCreate
    institute, employees, services = _bootstrap_reference_data(client)
    employee = employees[0]["id"]
    ticket, _, capture = prepare(main_module.engine, institute, employee, services[0]["id"])
    with Session(main_module.engine) as db:
        apply_capture(db, institute, capture, employee, "operator", "cb")
        identifiers = []
        for key, amount in (("partial", "5.10"), ("remaining", "5.25")):
            identifier = reserve(db, institute, ticket, key, amount).id
            request = seal_refund(db, institute, identifier)
            record_refund_outcome(db, institute, identifier, "provider", "account", ProviderResult("reference", ProviderStatus.REFUNDED, request.value))
            identifiers.append(identifier)
        first = decide_refund_loyalty(db, institute, identifiers[0], -6, "Explicit correction", "first", "manager")
        adjust(db, institute, first.customer_id, AdjustmentCreate(points=100, reason="Independent correction", idempotency_key="independent"), "manager")
        with pytest.raises(HTTPException):
            decide_refund_loyalty(db, institute, identifiers[1], -5, "Over original earning", "second", "manager")


def assert_decision_downgrade_refused(engine, monkeypatch):
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
        command.stamp(config, "93f0348baef2")
        with pytest.raises(RuntimeError, match="cannot preserve signed history"):
            command.downgrade(config, "82ef237a9df1")
