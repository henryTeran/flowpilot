from pathlib import Path
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import event, select, text
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.loyalty import service
from app.modules.loyalty.models import LoyaltyEntry
from app.modules.loyalty.schemas import AdjustmentCreate
from app.modules.customers.schemas import CustomerCreate
from app.modules.customers.service import create_customer
from app.shared.exceptions import business_error
from test_postgres_scheduling_4d import postgres_flow, race
from test_ticket_workflow import _auth_headers, _bootstrap_reference_data


def customer(engine, institute):
    with Session(engine) as db:
        return create_customer(db, institute, CustomerCreate(display_name="Loyalty client", idempotency_key="loyal-client"), "operator").id


def test_scoped_manual_points_history_replay_and_explicit_tiers(client, monkeypatch):
    institute, employees, services = _bootstrap_reference_data(client)
    identity = customer(main_module.engine, institute)
    prefix = f"/api/v1/loyalty/institutes/{institute}"
    path = prefix + f"/customers/{identity}"
    operator, manager = _auth_headers(institute_id=institute), _auth_headers("responsable_institut", institute)
    payload = dict(points=10, reason="Attribution explicite", idempotency_key="manual-credit")
    assert client.get(path, headers=operator).json() == dict(customer_id=identity, points=0, tier=None)
    for headers in (_auth_headers(institute_id=None), _auth_headers(institute_id="foreign"), _auth_headers("collaboratrice", institute)):
        assert client.get(path, headers=headers).status_code == 403
    assert client.post(path + "/adjustments", headers=operator, json=payload).status_code == 403
    for value in (True, 1.5, "10", 1_000_000_001):
        assert client.post(path + "/adjustments", headers=manager, json={**payload, "points": value}).status_code == 422
    assert client.post(path + "/adjustments", headers=manager, json={**payload, "points": 0}).status_code == 400
    tier = dict(name="Recognized", minimum_points=10, benefit_description="Avantage a definir explicitement", idempotency_key="tier")
    configured = client.post(prefix + "/tiers", headers=manager, json=tier)
    assert configured.status_code == 200
    assert client.post(prefix + "/tiers", headers=manager, json=tier).json() == configured.json()
    assert client.post(prefix + "/tiers", headers=manager, json={**tier, "name": "Different"}).status_code == 400
    assert client.post(prefix + "/tiers", headers=manager, json={**tier, "idempotency_key": "another"}).status_code == 400
    assert_downgrade_refused(main_module.engine, monkeypatch)  # Tier-only history must also survive downgrade.
    def fail(session, context, instances):
        if any(isinstance(row, LoyaltyEntry) for row in session.new):
            raise business_error("Injected point history failure")
    event.listen(Session, "before_flush", fail)
    try:
        assert client.post(path + "/adjustments", headers=manager, json=payload).status_code == 400
    finally:
        event.remove(Session, "before_flush", fail)
    assert client.get(path, headers=operator).json()["points"] == 0
    credit = client.post(path + "/adjustments", headers=manager, json=payload)
    assert credit.status_code == 200 and credit.json()["actor_id"] == "test-user"
    assert client.get(path, headers=operator).json()["tier"]["name"] == "Recognized"
    assert client.post(path + "/adjustments", headers=manager, json={**payload, "points": -11, "idempotency_key": "overdraw"}).status_code == 400
    correction = {**payload, "points": -3, "reason": "Correction explicite", "idempotency_key": "manual-debit"}
    assert client.post(path + "/adjustments", headers=manager, json=correction).status_code == 200
    assert client.get(path, headers=operator).json()["points"] == 7
    assert client.get(path, headers=operator).json()["tier"] is None
    assert client.post(path + "/adjustments", headers=manager, json=payload).json() == credit.json()
    assert client.post(path + "/adjustments", headers=manager, json={**payload, "reason": "Changed intent"}).status_code == 400
    rows = client.get(path + "/history", headers=operator).json()
    assert [row["points"] for row in rows] == [10, -3]
    assert client.get(prefix + "/customers/missing", headers=operator).status_code == 404
    assert_downgrade_refused(main_module.engine, monkeypatch)


def test_competing_point_corrections_cannot_overdraw(postgres_flow, monkeypatch):
    engine, institute, employee, care = postgres_flow
    identity = customer(engine, institute)
    with Session(engine) as db:
        service.adjust(db, institute, identity, AdjustmentCreate(points=7, reason="Initial grant", idempotency_key="initial"), "manager")
    results = race(engine, [lambda db, key=key: service.adjust(db, institute, identity,
        AdjustmentCreate(points=-5, reason="Correction", idempotency_key=key), "manager") for key in ("one", "two")])
    assert sorted(row[0] for row in results) == ["conflict", "ok"]
    with Session(engine) as db:
        assert service.points(db, institute, identity) == 2
        assert len(db.scalars(select(LoyaltyEntry)).all()) == 2
    assert_downgrade_refused(engine, monkeypatch)


def test_duplicate_point_grant_is_recorded_once(postgres_flow):
    engine, institute, employee, care = postgres_flow
    identity = customer(engine, institute)
    payload = AdjustmentCreate(points=10, reason="One grant", idempotency_key="one-grant")
    results = race(engine, [lambda db: service.adjust(db, institute, identity, payload, "manager")] * 2)
    assert results[0] == results[1] and results[0][0] == "ok"
    with Session(engine) as db:
        assert service.points(db, institute, identity) == 10
        assert len(db.scalars(select(LoyaltyEntry)).all()) == 1


def assert_downgrade_refused(engine, monkeypatch):
    from app.core.config import settings
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
        command.stamp(config, "e8ab23d0f358")
        with pytest.raises(RuntimeError, match="cannot preserve"):
            command.downgrade(config, "d7fa12cfe247")
