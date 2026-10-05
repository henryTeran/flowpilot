from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from threading import Barrier
from types import SimpleNamespace
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import event, select, text
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.gift_cards import service
from app.modules.gift_cards.models import GiftCard, GiftCardSettings
from app.modules.gift_cards.schemas import GiftCardIssue
from app.shared.exceptions import business_error
from app.shared.time import utcnow
from app.core.security import create_access_token
from test_postgres_scheduling_4d import postgres_flow, race
from test_ticket_workflow import _auth_headers, _bootstrap_reference_data
from test_checkout_customer_8e import prepare as prepare_checkout
from app.modules.tickets.models import QueueTicket
from app.modules.tickets.service import complete_payment


def payload(**changes):
    return {"amount": "25.10", "valid_days": 365, "reason": "Attribution commerciale", "idempotency_key": "gift-intent", **changes}


def test_gift_card_currency_scope_precision_replay_and_expiry(client, monkeypatch):
    institute, employees, services = _bootstrap_reference_data(client)
    manager, operator = _auth_headers("responsable_institut", institute), _auth_headers(institute_id=institute)
    prefix = f"/api/v1/gift-cards/institutes/{institute}"
    unidentified = create_access_token(subject="", extra_claims={"role": "responsable_institut", "institute_id": institute})
    assert client.post(prefix, headers={"Authorization": f"Bearer {unidentified}"}, json=payload()).status_code == 403
    assert client.post(prefix, headers=manager, json=payload()).status_code == 400
    assert client.put(prefix + "/settings", headers=operator, json={"currency": "CHF"}).status_code == 403
    assert client.put(prefix + "/settings", headers=_auth_headers("responsable_institut", "foreign"), json={"currency": "CHF"}).status_code == 403
    assert client.put(prefix + "/settings", headers=manager, json={"currency": "USD"}).status_code == 422
    configured = client.put(prefix + "/settings", headers=manager, json={"currency": "CHF"})
    assert configured.status_code == 200 and configured.json()["actor_id"] == "test-user"
    assert client.put(prefix + "/settings", headers=manager, json={"currency": "CHF"}).json() == configured.json()
    assert client.post(prefix, headers=operator, json=payload()).status_code == 403
    for amount in ("0", "-1", "1.001", "NaN", "Infinity", "100000000.00", True):
        assert client.post(prefix, headers=manager, json=payload(amount=amount)).status_code == 422
    assert client.post(prefix, headers=manager, json=payload(customer_id="customer_missing")).status_code == 404
    issued = client.post(prefix, headers=manager, json=payload())
    assert issued.status_code == 200, issued.text
    card = issued.json()
    assert Decimal(str(card["remaining"])) == Decimal("25.10") and card["currency"] == "CHF"
    assert card["status"] == "active" and len(card["code"]) >= 32
    assert client.post(prefix, headers=manager, json=payload(amount="25.1")).json() == card
    for change in ({"amount": "30"}, {"valid_days": 30}, {"reason": "Different grant"}, {"customer_id": "customer_missing"}):
        assert client.post(prefix, headers=manager, json=payload(**change)).status_code == 400
    assert client.put(prefix + "/settings", headers=manager, json={"currency": "EUR"}).status_code == 400
    assert client.get(prefix + "/settings", headers=operator).json()["currency"] == "CHF"
    lookup = client.post(prefix + "/lookup", headers=operator, json={"code": card["code"]})
    assert lookup.status_code == 200 and "code" not in lookup.json()
    assert client.post(prefix + "/lookup", headers=_auth_headers(institute_id="foreign"), json={"code": card["code"]}).status_code == 403
    assert client.post("/api/v1/gift-cards/institutes/foreign/lookup", headers=_auth_headers(institute_id="foreign"), json={"code": card["code"]}).status_code == 404
    assert client.post(prefix + "/lookup", headers=operator, json={"code": "X" * 32}).status_code == 404
    with Session(main_module.engine) as db:
        row = db.get(GiftCard, card["id"])
        assert row.actor_id == "test-user" and row.issuance_reason == payload()["reason"]
        expiry = service.aware(row.expires_at)
        assert service.card_view(row, expiry - timedelta(microseconds=1))["usable_amount"] == Decimal("25.10")
        assert service.card_view(row, expiry)["usable_amount"] == 0
    monkeypatch.setattr(service, "utcnow", lambda: expiry)
    replay = client.post(prefix, headers=manager, json=payload()).json()
    assert replay["status"] == "expired" and Decimal(str(replay["remaining"])) == Decimal("25.10")
    assert replay["code"] == card["code"] and Decimal(str(replay["usable_amount"])) == 0
    assert_downgrade_retains_credit(main_module.engine, monkeypatch)


def test_failed_issuance_creates_no_credit_and_can_retry(client):
    institute, employees, services = _bootstrap_reference_data(client)
    manager = _auth_headers("responsable_institut", institute)
    prefix = f"/api/v1/gift-cards/institutes/{institute}"
    assert client.put(prefix + "/settings", headers=manager, json={"currency": "EUR"}).status_code == 200
    def fail(db, context, instances):
        if any(isinstance(row, GiftCard) for row in db.new):
            raise business_error("Injected credit failure")
    event.listen(Session, "before_flush", fail)
    try:
        assert client.post(prefix, headers=manager, json=payload()).status_code == 400
    finally:
        event.remove(Session, "before_flush", fail)
    with Session(main_module.engine) as db:
        assert len(db.scalars(select(GiftCard)).all()) == 0
    assert client.post(prefix, headers=manager, json=payload()).json()["currency"] == "EUR"


def test_duplicate_card_issuance_credits_once(postgres_flow, monkeypatch):
    engine, institute, employee, care = postgres_flow
    with Session(engine) as db:
        service.configure_currency(db, institute, "CHF", "manager")
    intent = GiftCardIssue(**payload())
    results = race(engine, [lambda db: service.issue_card(db, institute, intent, "manager"),
                           lambda db: service.issue_card(db, institute, intent, "manager")])
    assert results[0] == results[1] and results[0][0] == "ok"
    with Session(engine) as db:
        cards = db.scalars(select(GiftCard)).all()
        assert len(cards) == 1 and cards[0].remaining == Decimal("25.10")
    assert_downgrade_retains_credit(engine, monkeypatch)


def test_currency_change_and_issuance_serialize_with_preloaded_settings(postgres_flow):
    engine, institute, employee, care = postgres_flow
    with Session(engine) as db:
        service.configure_currency(db, institute, "CHF", "manager")
    preloaded = Barrier(2)
    def change(db):
        cached = db.get(GiftCardSettings, institute)
        preloaded.wait(timeout=10)
        result = service.configure_currency(db, institute, "EUR", "manager")
        assert cached.currency == result.currency
        return result
    def issue(db):
        cached = db.get(GiftCardSettings, institute)
        preloaded.wait(timeout=10)
        result = service.issue_card(db, institute, GiftCardIssue(**payload()), "manager")
        assert cached.currency == result.currency
        return result
    # race() expects an id; settings are keyed by institute_id rather than id.
    def change_with_id(db):
        result = change(db)
        return SimpleNamespace(id=result.institute_id)
    results = race(engine, [change_with_id, issue])
    assert results[1][0] == "ok"
    with Session(engine) as db:
        assert db.scalar(select(GiftCard.currency)) == db.get(GiftCardSettings, institute).currency


def test_unbacked_gift_payment_labels_cannot_close_checkout(client):
    institute, employees, services = _bootstrap_reference_data(client)
    employee = employees[0]["id"]
    ticket, line, customers, package = prepare_checkout(main_module.engine, institute, employee, services[0]["id"])
    headers = _auth_headers(institute_id=institute)
    path = f"/api/v1/tickets/{ticket}/checkout/pay"
    for method in ("carte_cadeau", "mixte"):
        response = client.patch(path, headers=headers, json={"employee_id": employee, "payment_method": method})
        assert response.status_code == 400
    with Session(main_module.engine) as db:
        row = db.get(QueueTicket, ticket)
        assert row.status == "ready_for_checkout" and row.paid_at is None
        # Historical same-intent recovery remains compatible; no new settlement is claimed.
        row.status, row.paid_employee_id, row.payment_method = "paid", employee, "carte_cadeau"
        row.paid_at = utcnow()
        db.commit()
        assert complete_payment(db, ticket, employee, "carte_cadeau").id == ticket


def assert_downgrade_retains_credit(engine, monkeypatch):
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
        command.stamp(config, "b5d890adc025")
        with pytest.raises(RuntimeError, match="cannot preserve"):
            command.downgrade(config, "a4c789fcb914")
