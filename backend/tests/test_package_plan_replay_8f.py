from pathlib import Path
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select, text
from sqlalchemy.orm import Session

import app.main as main_module
from app.modules.commerce.models import PackagePlan
from app.modules.commerce.schemas import PackagePlanCreate
from app.modules.commerce.service import create_plan
from app.modules.services.models import Service
from test_postgres_scheduling_4d import postgres_flow, race
from test_ticket_workflow import _auth_headers, _bootstrap_reference_data


def test_configuration_replay_is_scoped_and_preserves_original_intent(client, monkeypatch):
    institute, employees, services = _bootstrap_reference_data(client)
    manager = _auth_headers("responsable_institut", institute)
    path = f"/api/v1/commerce/institutes/{institute}/package-plans"
    payload = {"name": "Cure visage", "service_id": services[0]["id"], "sessions": 5,
               "valid_days": 90, "idempotency_key": "configuration-intent"}
    assert client.post(path, headers=_auth_headers(institute_id=institute), json=payload).status_code == 403
    assert client.post(path, headers=_auth_headers("responsable_institut", "foreign"), json=payload).status_code == 403
    first = client.post(path, headers=manager, json=payload)
    assert first.status_code == 200, first.text
    assert client.post(path, headers=manager, json=payload).json() == first.json()
    for field, value in [("name", "Other"), ("service_id", services[1]["id"]), ("sessions", 6), ("valid_days", 100)]:
        assert client.post(path, headers=manager, json={**payload, field: value}).status_code == 400
    assert client.post(path, headers=manager, json={**payload, "idempotency_key": " "}).status_code == 422
    with Session(main_module.engine) as db:
        assert len(db.scalars(select(PackagePlan)).all()) == 1
        service = db.get(Service, payload["service_id"])
        service.status = "inactive"
        db.commit()
    assert client.post(path, headers=manager, json=payload).json() == first.json()
    assert client.post(path, headers=manager, json={**payload, "idempotency_key": "new-intent"}).status_code == 400
    with Session(main_module.engine) as db:
        db.get(Service, payload["service_id"]).status = "active"
        db.commit()
    legacy = {key: value for key, value in payload.items() if key != "idempotency_key"}
    assert client.post(path, headers=manager, json=legacy).status_code == 200
    assert client.post(path, headers=manager, json=legacy).status_code == 200
    assert_downgrade_retains_replay(main_module.engine, monkeypatch)


def test_same_configuration_intent_is_created_once_on_postgres(postgres_flow, monkeypatch):
    engine, institute, employee, service = postgres_flow
    payload = PackagePlanCreate(name="Cure", service_id=service, sessions=2,
                               valid_days=30, idempotency_key="concurrent-plan")
    results = race(engine, [lambda db: create_plan(db, institute, payload),
                           lambda db: create_plan(db, institute, payload)])
    assert results[0] == results[1] and results[0][0] == "ok"
    with Session(engine) as db:
        assert len(db.scalars(select(PackagePlan)).all()) == 1
    assert_downgrade_retains_replay(engine, monkeypatch)


def assert_downgrade_retains_replay(engine, monkeypatch):
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
        command.stamp(config, "e2a567da97f2")
        with pytest.raises(RuntimeError, match="cannot preserve"):
            command.downgrade(config, "d1f456c986e1")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "e2a567da97f2"
        assert connection.scalar(text("SELECT COUNT(*) FROM package_plans WHERE idempotency_key IS NOT NULL")) == 1
