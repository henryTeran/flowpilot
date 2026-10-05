from datetime import timedelta
from threading import Barrier
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from sqlalchemy import select, text
from sqlalchemy.orm import Session

import app.main as main_module
from app.modules.commerce.models import CustomerPackage, PackagePlan, PackageRedemption
from app.modules.commerce.schemas import PackageConsume, PackageIssue
from app.modules.commerce.service import consume_package, issue_package, reverse_package_consumption
from app.modules.planning.service import start_service_session, finish_service_session
from app.modules.tickets.models import QueueTicket, TicketLine, QueueEvent
from app.modules.tickets.schemas import TicketCreate
from app.modules.tickets.service import create_queue_ticket, complete_payment
from app.shared.time import utcnow
from test_postgres_scheduling_4d import postgres_flow, race
from test_ticket_workflow import _auth_headers, _bootstrap_reference_data


def prepared(engine, institute, employee, service):
    with Session(engine) as db:
        plan = PackagePlan(id="reverse-plan", institute_id=institute, service_id=service,
                           name="Cure", sessions=2, valid_days=30)
        db.add(plan)
        db.commit()
        package = issue_package(db, institute, PackageIssue(plan_id=plan.id, customer_id="reverse-client",
                                idempotency_key="reverse-issue"), "issuer")
        package_id = package.id
        ticket = create_queue_ticket(db, TicketCreate(institute_id=institute, service_id=service, customer_id="reverse-client"))
        ticket_id = ticket.id
        session = start_service_session(db, ticket.id, employee, service)
        finish_service_session(db, session.id)
        line = db.scalar(select(TicketLine).where(TicketLine.ticket_id == ticket.id))
        line_id, price = line.id, float(line.total)
        redemption = consume_package(db, institute, package_id,
            PackageConsume(ticket_line_id=line.id, idempotency_key="reverse-consume"), "operator")
        return package_id, ticket_id, line_id, redemption.id, price


def test_reversal_preserves_history_replay_expiry_and_atomic_price_restoration(client, monkeypatch):
    institute, employees, services = _bootstrap_reference_data(client)
    package, ticket, line, redemption, price = prepared(main_module.engine, institute, employees[0]["id"], services[0]["id"])
    manager = _auth_headers("responsable_institut", institute)
    operator = _auth_headers(institute_id=institute)
    prefix = f"/api/v1/commerce/institutes/{institute}"
    path = prefix + f"/package-redemptions/{redemption}/reverse"
    reason = {"reason": "Mauvais forfait choisi"}
    assert client.post(path, headers=operator, json=reason).status_code == 403
    assert client.post(path, headers=_auth_headers("responsable_institut", "foreign"), json=reason).status_code == 403
    assert client.post(path, headers=manager, json={"reason": " "}).status_code == 422
    from app.modules.commerce import service as commerce_service
    from app.shared.exceptions import business_error
    original = commerce_service.record_event
    def fail_after_flush(*args):
        original(*args)
        raise business_error("Injected reversal failure")
    with monkeypatch.context() as patch:
        patch.setattr(commerce_service, "record_event", fail_after_flush)
        assert client.post(path, headers=manager, json=reason).status_code == 400
    with Session(main_module.engine) as db:
        assert db.get(CustomerPackage, package).consumed == 1
        assert db.get(TicketLine, line).total == 0
        assert db.get(PackageRedemption, redemption).reversed_at is None
    reversed_row = client.post(path, headers=manager, json=reason)
    assert reversed_row.status_code == 200, reversed_row.text
    assert reversed_row.json()["reversed_at"] and reversed_row.json()["reversed_by"] == "test-user"
    assert client.post(path, headers=manager, json=reason).json() == reversed_row.json()
    assert client.post(path, headers=manager, json={"reason": "Changed"}).status_code == 400
    with Session(main_module.engine) as db:
        assert db.get(CustomerPackage, package).consumed == 0
        assert float(db.get(TicketLine, line).total) == float(db.get(QueueTicket, ticket).total_amount) == price
        assert len(db.scalars(select(QueueEvent).where(QueueEvent.event_type == "commerce.package_reversed")).all()) == 1
    consume = prefix + f"/packages/{package}/consume"
    payload = {"ticket_line_id": line, "idempotency_key": "reverse-consume"}
    assert client.post(consume, headers=operator, json=payload).json() == reversed_row.json()
    reapplied = client.post(consume, headers=operator, json={**payload, "idempotency_key": "new-consumption"})
    assert reapplied.status_code == 200 and reapplied.json()["id"] != redemption
    assert client.post(path, headers=manager, json=reason).json() == reversed_row.json()
    with Session(main_module.engine) as db:
        assert db.get(CustomerPackage, package).consumed == 1
        assert db.get(TicketLine, line).total == 0
        assert len(db.scalars(select(PackageRedemption)).all()) == 2
        row = db.get(CustomerPackage, package)
        row.expires_at = utcnow() - timedelta(seconds=1)
        row.issued_at = row.expires_at - timedelta(days=30)
        db.commit()
    assert client.post(prefix + f"/package-redemptions/{reapplied.json()['id']}/reverse", headers=manager, json=reason).status_code == 200
    view = client.get(prefix + "/packages?customer_id=reverse-client", headers=operator).json()[0]
    assert view["remaining"] == 2 and view["usable_sessions"] == 0 and view["status"] == "expired"
    assert client.post(consume, headers=operator, json={**payload, "idempotency_key": "expired-new"}).status_code == 400
    assert client.patch(f"/api/v1/tickets/{ticket}/cancel", headers=operator).status_code == 200


def test_paid_package_redemption_cannot_be_reversed(client):
    institute, employees, services = _bootstrap_reference_data(client)
    package, ticket, _, redemption, _ = prepared(main_module.engine, institute, employees[0]["id"], services[0]["id"])
    operator = _auth_headers(institute_id=institute)
    assert client.patch(f"/api/v1/tickets/{ticket}/checkout/pay", headers=operator,
        json={"employee_id": employees[0]["id"], "payment_method": "cb"}).status_code == 200
    response = client.post(f"/api/v1/commerce/institutes/{institute}/package-redemptions/{redemption}/reverse",
        headers=_auth_headers("responsable_institut", institute), json={"reason": "After payment"})
    assert response.status_code == 400
    with Session(main_module.engine) as db:
        assert db.get(CustomerPackage, package).consumed == 1
        assert db.get(PackageRedemption, redemption).reversed_at is None


def test_duplicate_reversals_cannot_credit_twice_with_cached_state(postgres_flow, monkeypatch):
    engine, institute, employee, service = postgres_flow
    package, ticket, line, redemption, price = prepared(engine, institute, employee, service)
    preloaded = Barrier(2)
    def reverse(db):
        cached = db.get(PackageRedemption, redemption)
        assert cached.reversed_at is None
        preloaded.wait(timeout=10)
        return reverse_package_consumption(db, institute, redemption, "Race reversal", "actor")
    assert race(engine, [reverse, reverse]) == [("ok", redemption), ("ok", redemption)]
    with Session(engine) as db:
        assert db.get(CustomerPackage, package).consumed == 0
        assert float(db.get(QueueTicket, ticket).total_amount) == float(db.get(TicketLine, line).total) == price
        assert len(db.scalars(select(QueueEvent).where(QueueEvent.event_type == "commerce.package_reversed")).all()) == 1
    assert_downgrade_preserves_reversal(engine, monkeypatch)


def test_payment_and_reversal_cannot_disagree_about_price_or_package_balance(postgres_flow):
    engine, institute, employee, service = postgres_flow
    package, ticket, line, redemption, price = prepared(engine, institute, employee, service)
    results = race(engine, [lambda db: reverse_package_consumption(db, institute, redemption, "Race payment", "actor"),
                            lambda db: complete_payment(db, ticket, employee, "cb")])
    assert results[1][0] == "ok"
    with Session(engine) as db:
        paid = db.get(QueueTicket, ticket)
        used = db.get(CustomerPackage, package).consumed
        assert paid.status == "paid"
        assert float(paid.total_amount) == float(db.get(TicketLine, line).total)
        assert (used, float(paid.total_amount)) in {(0, price), (1, 0.0)}
        assert (db.get(PackageRedemption, redemption).reversed_at is not None) == (used == 0)


def test_downgrade_refuses_to_reinterpret_reversed_history(client, monkeypatch):
    institute, employees, services = _bootstrap_reference_data(client)
    package, _, _, redemption, _ = prepared(main_module.engine, institute, employees[0]["id"], services[0]["id"])
    with Session(main_module.engine) as db:
        reverse_package_consumption(db, institute, redemption, "Preserve history", "actor")
    assert_downgrade_preserves_reversal(main_module.engine, monkeypatch)
    with Session(main_module.engine) as db:
        assert db.get(CustomerPackage, package).consumed == 0
        assert db.get(PackageRedemption, redemption).reversal_reason == "Preserve history"


def assert_downgrade_preserves_reversal(engine, monkeypatch):
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
        command.stamp(config, "head")
        with pytest.raises(RuntimeError, match="cannot preserve"):
            command.downgrade(config, "b9d234a764cf")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "c0e345b875d0"
