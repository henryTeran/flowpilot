from datetime import timedelta
from pathlib import Path
from threading import Barrier
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select, text
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.gift_cards.service import configure_currency
from app.modules.tickets.currency import confirm_currency
from app.modules.tickets.models import QueueTicket, TicketCurrencyFact, TicketLine
from app.modules.tickets.schemas import TicketCreate
from app.modules.tickets.service import create_queue_ticket, complete_payment
from app.modules.tickets.service import add_checkout_ticket_line
from fastapi import HTTPException
from app.shared.time import utcnow
from test_checkout_customer_8e import prepare as prepare_checkout
from test_postgres_scheduling_4d import postgres_flow, race
from test_ticket_workflow import _auth_headers, _bootstrap_reference_data


def test_creation_snapshot_replay_and_booking_checkout_currency(client):
    institute, employees, services = _bootstrap_reference_data(client)
    operator, manager = _auth_headers(institute_id=institute), _auth_headers("responsable_institut", institute)
    cfg = f"/api/v1/gift-cards/institutes/{institute}/settings"
    intent = {"institute_id": institute, "service_id": services[0]["id"], "idempotency_key": "old-untyped-arrival"}
    old = client.post("/api/v1/tickets", headers=operator, json=intent).json()
    assert old["currency"] is None
    assert client.put(cfg, headers=manager, json={"currency": "CHF"}).status_code == 200
    assert client.post("/api/v1/tickets", headers=operator, json=intent).json()["currency"] is None
    typed_intent = {**intent, "idempotency_key": "typed-arrival"}
    typed = client.post("/api/v1/tickets", headers=operator, json=typed_intent).json()
    assert typed["currency"] == "CHF"
    assert client.put(cfg, headers=manager, json={"currency": "EUR"}).status_code == 200
    assert client.post("/api/v1/tickets", headers=operator, json=typed_intent).json()["currency"] == "CHF"
    assert client.post("/api/v1/tickets", headers=operator, json={**intent, "idempotency_key": "new-eur-arrival"}).json()["currency"] == "EUR"
    booking = client.post("/api/v1/appointments", headers=operator, json={"institute_id": institute,
        "service_id": services[0]["id"], "employee_id": employees[0]["id"], "customer_name": "Currency booking",
        "start_time": (utcnow() + timedelta(minutes=1)).isoformat(), "idempotency_key": "currency-booking"}).json()
    path = f"/api/v1/appointments/{booking['id']}"
    assert client.patch(path + "/start", headers=operator).status_code == 200
    completed = client.patch(path + "/complete", headers=operator).json()
    with Session(main_module.engine) as db:
        ticket = db.get(QueueTicket, completed["checkout_ticket_id"])
        assert ticket.currency == "EUR"
        assert ticket.total_amount == db.scalar(select(TicketLine.total).where(TicketLine.ticket_id == ticket.id))
        facts = db.scalars(select(TicketCurrencyFact)).all()
        assert len(facts) == 3 and all(row.source == "institute_settings" and row.actor_id == "test-user" for row in facts)


def test_unpaid_legacy_confirmation_scope_status_replay_and_rollback(client, monkeypatch):
    institute, employees, services = _bootstrap_reference_data(client)
    employee = employees[0]["id"]
    ticket, line, customers, package = prepare_checkout(main_module.engine, institute, employee, services[0]["id"])
    operator, manager = _auth_headers(institute_id=institute), _auth_headers("responsable_institut", institute)
    path = f"/api/v1/tickets/{ticket}/currency"
    payload = {"currency": "CHF", "reason": "Confirmation explicite du devis"}
    assert client.patch(path, headers=operator, json=payload).status_code == 400
    assert client.put(f"/api/v1/gift-cards/institutes/{institute}/settings", headers=manager, json={"currency": "CHF"}).status_code == 200
    assert client.patch(path, headers=_auth_headers(institute_id="foreign"), json=payload).status_code == 403
    assert client.patch(path, headers=_auth_headers(institute_id=None), json=payload).status_code == 403
    assert client.patch(path, headers=_auth_headers("collaboratrice", institute), json=payload).status_code == 403
    assert client.patch(path, headers=operator, json={**payload, "currency": "EUR"}).status_code == 400
    from app.modules.tickets import currency as currency_module
    from app.shared.exceptions import business_error
    original = currency_module.record_event
    def fail(*args):
        original(*args)
        raise business_error("Injected confirmation failure")
    with Session(main_module.engine) as db:
        price = db.get(TicketLine, line).total
    with monkeypatch.context() as patch:
        patch.setattr(currency_module, "record_event", fail)
        assert client.patch(path, headers=operator, json=payload).status_code == 400
    with Session(main_module.engine) as db:
        assert db.get(QueueTicket, ticket).currency is None
        assert not db.scalars(select(TicketCurrencyFact)).all()
    bound = client.patch(path, headers=operator, json=payload)
    assert bound.status_code == 200, bound.text
    assert client.patch(path, headers=operator, json=payload).json() == bound.json()
    assert client.patch(path, headers=operator, json={**payload, "currency": "EUR"}).status_code == 400
    with Session(main_module.engine) as db:
        assert db.get(TicketLine, line).total == db.get(QueueTicket, ticket).total_amount == price
        facts = db.scalars(select(TicketCurrencyFact)).all()
        assert len(facts) == 1 and facts[0].reason == payload["reason"] and facts[0].actor_id == "test-user"
        complete_payment(db, ticket, employee, "cb")
    assert client.patch(path, headers=operator, json=payload).status_code == 200
    assert_downgrade_keeps_currency(main_module.engine, monkeypatch)


def test_currency_confirmation_cannot_relabel_an_untyped_paid_ticket(client):
    institute, employees, services = _bootstrap_reference_data(client)
    ticket, line, customers, package = prepare_checkout(main_module.engine, institute, employees[0]["id"], services[0]["id"])
    with Session(main_module.engine) as db:
        complete_payment(db, ticket, employees[0]["id"], "cb")
        configure_currency(db, institute, "CHF", "manager")
    assert client.patch(f"/api/v1/tickets/{ticket}/currency", headers=_auth_headers(institute_id=institute),
        json={"currency": "CHF", "reason": "Cannot reinterpret paid history"}).status_code == 400


def test_new_catalog_prices_require_confirmed_matching_invoice_currency(client):
    institute, employees, services = _bootstrap_reference_data(client)
    ticket, line, customers, package = prepare_checkout(main_module.engine, institute, employees[0]["id"], services[0]["id"])
    with Session(main_module.engine) as db:
        configure_currency(db, institute, "CHF", "manager")
        original_total = db.get(QueueTicket, ticket).total_amount
        with pytest.raises(HTTPException, match="Confirmer la devise"):
            add_checkout_ticket_line(db, ticket, services[0]["id"])
        db.rollback()
        confirm_currency(db, ticket, "CHF", "Explicit invoice denomination", "operator")
        configure_currency(db, institute, "EUR", "manager")
        with pytest.raises(HTTPException, match="devises differentes"):
            add_checkout_ticket_line(db, ticket, services[0]["id"])
        db.rollback()
        assert db.get(QueueTicket, ticket).total_amount == original_total
        assert len(db.scalars(select(TicketLine).where(TicketLine.ticket_id == ticket)).all()) == 1
        configure_currency(db, institute, "CHF", "manager")
        assert add_checkout_ticket_line(db, ticket, services[0]["id"]).total_amount > original_total


def test_concurrent_confirmation_records_one_fact_with_cached_ticket(postgres_flow, monkeypatch):
    engine, institute, employee, care = postgres_flow
    ticket, line, customers, package = prepare_checkout(engine, institute, employee, care)
    with Session(engine) as db:
        configure_currency(db, institute, "CHF", "manager")
    barrier = Barrier(2)
    def confirm(db):
        cached = db.get(QueueTicket, ticket)
        barrier.wait(timeout=10)
        result = confirm_currency(db, ticket, "CHF", "Same quote", "operator")
        assert cached.currency == result.currency
        return result
    assert race(engine, [confirm, confirm]) == [("ok", ticket), ("ok", ticket)]
    with Session(engine) as db:
        assert len(db.scalars(select(TicketCurrencyFact)).all()) == 1
    assert_downgrade_keeps_currency(engine, monkeypatch)


def test_confirmation_and_payment_cannot_relabel_after_closure(postgres_flow):
    engine, institute, employee, care = postgres_flow
    ticket, line, customers, package = prepare_checkout(engine, institute, employee, care)
    with Session(engine) as db:
        configure_currency(db, institute, "CHF", "manager")
    results = race(engine, [lambda db: confirm_currency(db, ticket, "CHF", "Quote confirmed", "operator"),
                           lambda db: complete_payment(db, ticket, employee, "cb")])
    assert results[1][0] == "ok"
    with Session(engine) as db:
        assert db.get(QueueTicket, ticket).status == "paid"
        assert db.get(QueueTicket, ticket).currency == ("CHF" if results[0][0] == "ok" else None)


def assert_downgrade_keeps_currency(engine, monkeypatch):
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
        command.stamp(config, "c6e901bed136")
        with pytest.raises(RuntimeError, match="cannot preserve"):
            command.downgrade(config, "b5d890adc025")
