from decimal import Decimal
from sqlalchemy import event, select
from sqlalchemy.orm import Session
from threading import Barrier
import pytest
import app.main as main_module
from app.modules.loyalty import earning, service
from app.modules.loyalty.models import LoyaltyEarning, LoyaltyEntry
from app.modules.loyalty.schemas import EarningPolicyCreate
from app.modules.gift_cards.service import configure_currency, issue_card
from app.modules.gift_cards.schemas import GiftCardIssue, AllocationCreate
from app.modules.gift_cards.tenders import allocate
from app.modules.tickets.currency import confirm_currency
from app.modules.tickets.models import QueueTicket, TicketLine
from app.modules.tickets.service import complete_payment
from app.shared.exceptions import business_error
from test_membership_benefits_8h import prepare
from test_postgres_scheduling_4d import postgres_flow, race
from test_ticket_workflow import _auth_headers, _bootstrap_reference_data


def payload(**changes):
    return dict(currency="CHF", points_per_unit="1.5", enabled=True, reason="Programme explicite", idempotency_key="earning-policy", **changes)


def setup(engine, institute, employee, care, basis="10.35", anonymous=False):
    ticket, line, customers, package, member = prepare(engine, institute, employee, care)
    with Session(engine) as db:
        configure_currency(db, institute, "CHF", "manager")
        confirm_currency(db, ticket, "CHF", "Quote confirmation", "operator")
        db.get(TicketLine, line).unit_price = Decimal(basis)
        db.get(TicketLine, line).total = Decimal(basis)
        db.get(QueueTicket, ticket).total_amount = Decimal(basis)
        if anonymous:
            db.get(QueueTicket, ticket).customer_id = None
        db.commit()
    return ticket, line, customers[0]


def test_policy_scope_revision_replay_and_currency_freeze(client, monkeypatch):
    institute, employees, services = _bootstrap_reference_data(client)
    path = f"/api/v1/loyalty/institutes/{institute}"
    manager, operator = _auth_headers("responsable_institut", institute), _auth_headers(institute_id=institute)
    assert client.get(path + "/earning-policy", headers=operator).json() is None
    assert client.post(path + "/earning-policies", headers=manager, json=payload()).status_code == 400
    assert client.put(f"/api/v1/gift-cards/institutes/{institute}/settings", headers=manager, json={"currency": "CHF"}).status_code == 200
    for headers in (operator, _auth_headers("responsable_institut", None), _auth_headers("responsable_institut", "foreign")):
        assert client.post(path + "/earning-policies", headers=headers, json=payload()).status_code == 403
    for rate in ("0", "NaN", "Infinity", "10000.0001", "0.00001"):
        assert client.post(path + "/earning-policies", headers=manager, json={**payload(), "points_per_unit": rate}).status_code == 422
    first = client.post(path + "/earning-policies", headers=manager, json=payload())
    assert first.status_code == 200 and first.json()["revision"] == 1
    assert client.post(path + "/earning-policies", headers=manager, json=payload()).json() == first.json()
    assert client.post(path + "/earning-policies", headers=manager, json={**payload(), "points_per_unit": "2"}).status_code == 400
    paused = client.post(path + "/earning-policies", headers=manager, json={**payload(), "enabled": False, "idempotency_key": "pause"})
    assert paused.status_code == 200 and paused.json()["revision"] == 2
    assert client.post(path + "/earning-policies", headers=manager, json=payload()).json() == first.json()
    assert client.get(path + "/earning-policy", headers=operator).json() == paused.json()
    assert client.put(f"/api/v1/gift-cards/institutes/{institute}/settings", headers=manager, json={"currency": "EUR"}).status_code == 400
    assert_earning_downgrade_refused(main_module.engine, monkeypatch)


@pytest.mark.parametrize("gift", [False, True])
def test_checkout_awards_effective_invoice_once_and_rolls_back_all_facts(client, monkeypatch, gift):
    institute, employees, services = _bootstrap_reference_data(client)
    employee = employees[0]["id"]
    ticket, line, identity = setup(main_module.engine, institute, employee, services[0]["id"])
    operator, manager = _auth_headers(institute_id=institute), _auth_headers("responsable_institut", institute)
    path = f"/api/v1/loyalty/institutes/{institute}"
    policy = client.post(path + "/earning-policies", headers=manager, json=payload()).json()
    if gift:
        with Session(main_module.engine) as db:
            card = issue_card(db, institute, GiftCardIssue(amount="20", valid_days=30, reason="Grant", idempotency_key="gift"), "manager")
            allocate(db, institute, card.id, AllocationCreate(ticket_id=ticket, amount="10.35", idempotency_key="cover"), "operator")
    payment = dict(employee_id=employee, payment_method="carte_cadeau" if gift else "cb")
    pay = f"/api/v1/tickets/{ticket}/checkout/pay"
    def fail(db, context, instances):
        if any(isinstance(row, LoyaltyEarning) for row in db.new):
            raise business_error("Injected earning failure")
    event.listen(Session, "before_flush", fail)
    try:
        assert client.patch(pay, headers=operator, json=payment).status_code == 400
    finally:
        event.remove(Session, "before_flush", fail)
    with Session(main_module.engine) as db:
        assert db.get(QueueTicket, ticket).status == "ready_for_checkout"
        assert service.points(db, institute, identity) == 0
        assert db.get(LoyaltyEarning, ticket) is None
    assert client.patch(pay, headers=_auth_headers(institute_id=None), json=payment).status_code == 403
    assert client.patch(pay, headers=operator, json=payment).status_code == 200
    client.post(path + "/earning-policies", headers=manager, json={**payload(), "points_per_unit": "3", "idempotency_key": "new-rate"})
    assert client.patch(pay, headers=operator, json=payment).status_code == 200
    assert client.get(path + f"/customers/{identity}", headers=operator).json()["points"] == 15
    facts = client.get(path + f"/customers/{identity}/earnings", headers=operator).json()
    assert len(facts) == 1 and facts[0]["policy_id"] == policy["id"]
    assert Decimal(facts[0]["basis_amount"]) == Decimal("10.35") and Decimal(facts[0]["points_per_unit"]) == Decimal("1.5")
    assert facts[0]["actor_id"] == "test-user" and facts[0]["points"] == 15
    assert client.post("/api/v1/dev/reset-demo", headers=manager, params={"institute_id": institute}).status_code == 400
    assert_earning_downgrade_refused(main_module.engine, monkeypatch)


@pytest.mark.parametrize("kind", ["zero", "anonymous", "disabled", "historical"])
def test_no_invented_points_for_zero_anonymous_disabled_or_historical_checkout(client, kind):
    institute, employees, services = _bootstrap_reference_data(client)
    employee = employees[0]["id"]
    ticket, line, identity = setup(main_module.engine, institute, employee, services[0]["id"], anonymous=kind == "anonymous")
    operator, manager = _auth_headers(institute_id=institute), _auth_headers("responsable_institut", institute)
    pay = f"/api/v1/tickets/{ticket}/checkout/pay"
    payment = dict(employee_id=employee, payment_method="cb")
    if kind == "zero":
        prefix = f"/api/v1/commerce/institutes/{institute}"
        package = client.get(prefix + "/packages", headers=operator, params={"customer_id": identity}).json()[0]
        assert client.post(prefix + f"/packages/{package['id']}/consume", headers=operator,
            json={"ticket_line_id": line, "idempotency_key": "package-cover"}).status_code == 200
    if kind == "historical":
        assert client.patch(pay, headers=operator, json=payment).status_code == 200
    client.post(f"/api/v1/loyalty/institutes/{institute}/earning-policies", headers=manager, json={**payload(), "enabled": kind != "disabled"})
    assert client.patch(pay, headers=operator, json=payment).status_code == 200
    with Session(main_module.engine) as db:
        assert service.points(db, institute, identity) == 0
        fact = db.get(LoyaltyEarning, ticket)
        assert (fact is not None) == (kind == "zero")
        if fact:
            assert fact.points == 0 and fact.entry_id is None


def test_member_discount_earns_on_reduced_price_and_legacy_currency_requires_confirmation(client):
    from app.modules.services.models import Service
    institute, employees, services = _bootstrap_reference_data(client)
    employee, care = employees[0]["id"], services[0]["id"]
    ticket, line, customers, package, member = prepare(main_module.engine, institute, employee, care)
    operator, manager = _auth_headers(institute_id=institute), _auth_headers("responsable_institut", institute)
    with Session(main_module.engine) as db:
        configure_currency(db, institute, "CHF", "manager")
        earning.create_policy(db, institute, EarningPolicyCreate(**payload()), "manager")
        db.get(Service, care).price_member = Decimal("2.75")
        db.commit()
    pay = f"/api/v1/tickets/{ticket}/checkout/pay"
    payment = dict(employee_id=employee, payment_method="cb")
    assert client.patch(pay, headers=operator, json=payment).status_code == 400
    with Session(main_module.engine) as db:
        assert db.get(QueueTicket, ticket).status == "ready_for_checkout"
    assert client.patch(f"/api/v1/tickets/{ticket}/currency", headers=operator,
        json={"currency": "CHF", "reason": "Confirmation explicite"}).status_code == 200
    assert client.post(f"/api/v1/memberships/institutes/{institute}/{member}/benefits", headers=operator,
        json={"ticket_line_id": line, "idempotency_key": "member-price"}).status_code == 200
    assert client.patch(pay, headers=operator, json=payment).status_code == 200
    with Session(main_module.engine) as db:
        fact = db.get(LoyaltyEarning, ticket)
        assert fact.basis_amount == Decimal("2.75") and fact.points == 4
        assert service.points(db, institute, customers[0]) == 4


def test_duplicate_payment_awards_once_with_preloaded_policy(postgres_flow):
    engine, institute, employee, care = postgres_flow
    ticket, line, identity = setup(engine, institute, employee, care)
    with Session(engine) as db:
        earning.create_policy(db, institute, EarningPolicyCreate(**payload()), "manager")
    barrier = Barrier(2)
    def pay(db):
        cached = earning.current_policy(db, institute)
        barrier.wait(timeout=10)
        result = complete_payment(db, ticket, employee, "cb", actor="operator", operator_institute=institute)
        assert cached.points_per_unit == Decimal("1.5")
        return result
    results = race(engine, [pay] * 2)
    assert results == [("ok", ticket)] * 2
    with Session(engine) as db:
        assert service.points(db, institute, identity) == 15
        assert len(db.scalars(select(LoyaltyEarning)).all()) == 1


def test_rate_change_and_payment_snapshot_one_complete_revision(postgres_flow):
    engine, institute, employee, care = postgres_flow
    ticket, line, identity = setup(engine, institute, employee, care)
    with Session(engine) as db:
        first = earning.create_policy(db, institute, EarningPolicyCreate(**payload()), "manager").id
    results = race(engine, [lambda db: complete_payment(db, ticket, employee, "cb", actor="operator", operator_institute=institute),
        lambda db: earning.create_policy(db, institute, EarningPolicyCreate(**{**payload(), "points_per_unit": "3", "idempotency_key": "changed"}), "manager")])
    assert all(row[0] == "ok" for row in results)
    with Session(engine) as db:
        fact = db.get(LoyaltyEarning, ticket)
        assert (fact.policy_id, fact.points, fact.points_per_unit) in ((first, 15, Decimal("1.5")), (results[1][1], 31, Decimal("3")))
        assert service.points(db, institute, identity) == fact.points


def test_currency_change_and_policy_creation_cannot_mix_units(postgres_flow):
    engine, institute, employee, care = postgres_flow
    with Session(engine) as db:
        configure_currency(db, institute, "CHF", "manager")
    results = race(engine, [lambda db: configure_currency(db, institute, "EUR", "manager"),
        lambda db: earning.create_policy(db, institute, EarningPolicyCreate(**payload()), "manager")])
    assert sorted(row[0] for row in results) == ["conflict", "ok"]
    from app.modules.gift_cards.models import GiftCardSettings
    with Session(engine) as db:
        policy = earning.current_policy(db, institute)
        assert db.get(GiftCardSettings, institute).currency == ("CHF" if policy else "EUR")


def assert_earning_downgrade_refused(engine, monkeypatch):
    from app.core.config import settings
    from pathlib import Path
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text
    url = engine.url
    if engine.dialect.name == "postgresql":
        with engine.connect() as connection:
            schema = connection.scalar(text("SELECT current_schema()"))
        assert schema.startswith("fp_test_")
        url = url.update_query_dict({"options": f"-csearch_path={schema}"})
    config = Config(); config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
    with monkeypatch.context() as patch:
        patch.setattr(settings, "DATABASE_URL", url.render_as_string(hide_password=False))
        command.stamp(config, "f9bc34e10469")
        with pytest.raises(RuntimeError, match="cannot preserve"):
            command.downgrade(config, "e8ab23d0f358")
