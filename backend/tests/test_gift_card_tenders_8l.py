from datetime import timedelta
from decimal import Decimal
from threading import Barrier
from pathlib import Path
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select, text
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.gift_cards import tenders
from app.modules.gift_cards.models import GiftCard, GiftCardAllocation, GiftTenderClosure
from app.modules.gift_cards.schemas import GiftCardIssue, AllocationCreate
from app.modules.gift_cards.service import configure_currency, issue_card, card_view
from app.modules.tickets.currency import confirm_currency
from app.modules.tickets.models import QueueTicket, TicketLine
from app.modules.tickets.service import complete_payment
from app.modules.tickets.service import create_queue_ticket
from app.modules.tickets.schemas import TicketCreate
from app.modules.planning.service import start_service_session, finish_service_session
from app.shared.exceptions import business_error
from app.shared.time import utcnow
from test_membership_benefits_8h import prepare
from test_ticket_workflow import _auth_headers, _bootstrap_reference_data
from test_postgres_scheduling_4d import postgres_flow, race


def setup(engine, institute, employee, care, amount="100", ticket_currency="CHF"):
    ticket, line, customers, package, member = prepare(engine, institute, employee, care)
    with Session(engine) as db:
        if ticket_currency:
            configure_currency(db, institute, ticket_currency, "manager")
            confirm_currency(db, ticket, ticket_currency, "Explicit quote confirmation", "operator")
        configure_currency(db, institute, "CHF", "manager")
        card = issue_card(db, institute, GiftCardIssue(amount=amount, valid_days=30,
            reason="Commercial grant", idempotency_key="grant"), "manager")
        return ticket, line, customers, package, member, card.id


def test_partial_tender_guards_reversal_expiry_and_replay(client, monkeypatch):
    institute, employees, services = _bootstrap_reference_data(client)
    employee, care = employees[0]["id"], services[0]["id"]
    ticket, line, customers, package, member, card = setup(main_module.engine, institute, employee, care)
    operator, manager = _auth_headers(institute_id=institute), _auth_headers("responsable_institut", institute)
    root = f"/api/v1/gift-cards/institutes/{institute}"
    path = root + f"/{card}/allocations"
    payload = dict(ticket_id=ticket, amount="5.00", idempotency_key="debit")
    for headers in (_auth_headers(institute_id=None), _auth_headers(institute_id="foreign"), _auth_headers("collaboratrice", institute)):
        assert client.post(path, headers=headers, json=payload).status_code == 403
    for amount in ("0", "-1", "0.001", "NaN"):
        assert client.post(path, headers=operator, json={**payload, "amount": amount}).status_code == 422
    original = tenders.record_event
    def fail(*args):
        original(*args)
        raise business_error("Injected tender rollback")
    with monkeypatch.context() as patch:
        patch.setattr(tenders, "record_event", fail)
        assert client.post(path, headers=operator, json=payload).status_code == 400
    with Session(main_module.engine) as db:
        assert db.get(GiftCard, card).remaining == Decimal("100")
        assert not db.scalars(select(GiftCardAllocation)).all()
        price = db.get(TicketLine, line).total
    paid = client.post(path, headers=operator, json=payload)
    assert paid.status_code == 200, paid.text
    allocation = paid.json()
    assert "code" not in allocation
    assert client.post(path, headers=operator, json=payload).json() == allocation
    assert client.post(path, headers=operator, json={**payload, "amount": "6"}).status_code == 400
    view = client.get(root + f"/tickets/{ticket}/tenders", headers=operator).json()
    assert Decimal(view["total"]) == price and Decimal(view["gift_amount"]) == 5
    assert Decimal(view["remaining_due"]) == price - 5
    assert client.patch(f"/api/v1/tickets/{ticket}/cancel", headers=operator).status_code == 400
    assert client.patch(f"/api/v1/tickets/{ticket}/customer", headers=operator, json={"customer_id": customers[1]}).status_code == 400
    assert client.patch(f"/api/v1/tickets/{ticket}/checkout/lines/add", headers=operator, json={"service_id": care}).status_code == 400
    assert client.post(f"/api/v1/commerce/institutes/{institute}/packages/{package}/consume", headers=operator,
        json={"ticket_line_id": line, "idempotency_key": "covered"}).status_code == 400
    assert client.post(f"/api/v1/memberships/institutes/{institute}/{member}/benefits", headers=operator,
        json={"ticket_line_id": line, "idempotency_key": "benefit"}).status_code == 400
    pay = f"/api/v1/tickets/{ticket}/checkout/pay"
    for method in ("cb", "carte_cadeau", "mixte"):
        assert client.patch(pay, headers=operator, json={"employee_id": employee, "payment_method": method}).status_code == 400
    reverse = root + f"/allocations/{allocation['id']}/reverse"
    reason = {"reason": "Correction avant paiement"}
    assert client.post(reverse, headers=operator, json=reason).status_code == 403
    with monkeypatch.context() as patch:
        patch.setattr(tenders, "record_event", fail)
        assert client.post(reverse, headers=manager, json=reason).status_code == 400
    with Session(main_module.engine) as db:
        assert db.get(GiftCard, card).remaining == 95
        assert db.get(GiftCardAllocation, allocation["id"]).reversed_at is None
        db.get(GiftCard, card).issued_at = utcnow() - timedelta(days=31)
        db.get(GiftCard, card).expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    reversed_fact = client.post(reverse, headers=manager, json=reason)
    assert reversed_fact.status_code == 200
    assert client.post(reverse, headers=manager, json=reason).json() == reversed_fact.json()
    assert client.post(reverse, headers=manager, json={"reason": "Another reason"}).status_code == 400
    assert client.post(path, headers=operator, json=payload).json() == reversed_fact.json()
    assert client.post(path, headers=operator, json={**payload, "idempotency_key": "new-debit"}).status_code == 400
    with Session(main_module.engine) as db:
        assert db.get(GiftCard, card).remaining == 100
        assert card_view(db.get(GiftCard, card))["usable_amount"] == 0
        assert db.get(TicketLine, line).total == price
    assert client.patch(pay, headers=operator, json={"employee_id": employee, "payment_method": "cb"}).status_code == 200
    assert client.post("/api/v1/dev/reset-demo", params={"institute_id": institute}, headers=manager).status_code == 400
    assert_downgrade_refused(main_module.engine, monkeypatch)


@pytest.mark.parametrize("ticket_currency", [None, "EUR"])
def test_unknown_and_different_ticket_currencies_cannot_consume_credit(client, ticket_currency):
    institute, employees, services = _bootstrap_reference_data(client)
    ticket, line, customers, package, member, card = setup(main_module.engine, institute,
        employees[0]["id"], services[0]["id"], ticket_currency=ticket_currency)
    operator = _auth_headers(institute_id=institute)
    response = client.post(f"/api/v1/gift-cards/institutes/{institute}/{card}/allocations", headers=operator,
        json={"ticket_id": ticket, "amount": "5", "idempotency_key": "different-unit"})
    assert response.status_code == 400
    with Session(main_module.engine) as db:
        assert db.get(GiftCard, card).remaining == 100
        assert not db.scalars(select(GiftCardAllocation)).all()


@pytest.mark.parametrize("mixed", [False, True])
def test_gift_and_mixed_closure_preserve_revenue_and_recover_intent(client, monkeypatch, mixed):
    institute, employees, services = _bootstrap_reference_data(client)
    employee = employees[0]["id"]
    ticket, line, customers, package, member, card = setup(main_module.engine, institute, employee, services[0]["id"])
    operator, manager = _auth_headers(institute_id=institute), _auth_headers("responsable_institut", institute)
    root = f"/api/v1/gift-cards/institutes/{institute}"
    with Session(main_module.engine) as db:
        price = db.get(TicketLine, line).total
    amount = Decimal("5") if mixed else price
    intent = dict(ticket_id=ticket, amount=str(amount), idempotency_key="closure-debit")
    result = client.post(root + f"/{card}/allocations", headers=operator, json=intent)
    assert result.status_code == 200, result.text
    allocation = result.json()
    payment = dict(employee_id=employee, payment_method="mixte" if mixed else "carte_cadeau")
    if mixed:
        payment["remainder_method"] = "cb"
    path = f"/api/v1/tickets/{ticket}/checkout/pay"
    from app.modules.tickets import service as ticket_service
    def fail(*args):
        raise business_error("Injected closure failure")
    with monkeypatch.context() as patch:
        patch.setattr(ticket_service, "transition_ticket", fail)
        assert client.patch(path, headers=operator, json=payment).status_code == 400
    with Session(main_module.engine) as db:
        assert db.get(GiftTenderClosure, ticket) is None
        assert db.get(QueueTicket, ticket).status == "ready_for_checkout"
    assert client.patch(path, headers=_auth_headers(institute_id=None), json=payment).status_code == 403
    closed = client.patch(path, headers=operator, json=payment)
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "paid"
    assert client.patch(path, headers=operator, json=payment).json() == closed.json()
    view = client.get(root + f"/tickets/{ticket}/tenders", headers=operator).json()
    assert Decimal(view["remaining_due"]) == 0
    assert Decimal(view["remainder_amount"]) == price - amount
    assert view["remainder_method"] == ("cb" if mixed else None)
    assert client.patch(path, headers=operator, json={**payment, "remainder_method": "cheque"}).status_code == 400
    assert client.post(root + f"/{card}/allocations", headers=operator, json=intent).json() == allocation
    assert client.post(root + f"/allocations/{allocation['id']}/reverse", headers=manager,
        json={"reason": "Cannot reverse paid invoice"}).status_code == 400
    with Session(main_module.engine) as db:
        fact = db.get(GiftTenderClosure, ticket)
        assert fact.gift_amount == amount and fact.remainder_amount == price - amount
        assert fact.remainder_method == ("cb" if mixed else None) and fact.actor_id == "test-user"
        assert db.get(TicketLine, line).total == db.get(QueueTicket, ticket).total_amount == price
        assert db.get(GiftCard, card).remaining == 100 - amount
    assert_downgrade_refused(main_module.engine, monkeypatch)


def test_multiple_cards_cannot_overpay_and_leave_service_prices_intact(client):
    institute, employees, services = _bootstrap_reference_data(client)
    employee = employees[0]["id"]
    ticket, line, customers, package, member, first = setup(main_module.engine, institute, employee, services[0]["id"])
    with Session(main_module.engine) as db:
        total = db.get(TicketLine, line).total
        half = (total / 2).quantize(Decimal("0.01"))
        second = issue_card(db, institute, GiftCardIssue(amount="100", valid_days=30,
            reason="Second commercial grant", idempotency_key="second-card"), "manager").id
        tenders.allocate(db, institute, first, AllocationCreate(ticket_id=ticket, amount=half, idempotency_key="first-half"), "operator")
    operator = _auth_headers(institute_id=institute)
    path = f"/api/v1/gift-cards/institutes/{institute}/{second}/allocations"
    intent = dict(ticket_id=ticket, amount=str(total - half), idempotency_key="second-half")
    assert client.post(path, headers=operator, json={**intent, "amount": str(total - half + Decimal("0.01"))}).status_code == 400
    assert client.post(path, headers=operator, json=intent).status_code == 200
    with Session(main_module.engine) as db:
        assert tenders.tender_view(db, db.get(QueueTicket, ticket))["remaining_due"] == 0
        complete_payment(db, ticket, employee, "carte_cadeau", actor="operator")
        assert db.get(TicketLine, line).total == total
        assert db.get(GiftCard, first).remaining == 100 - half
        assert db.get(GiftCard, second).remaining == 100 - (total - half)


def test_concurrent_debits_cannot_overspend_preloaded_balance(postgres_flow):
    engine, institute, employee, care = postgres_flow
    ticket, line, customers, package, member, card = setup(engine, institute, employee, care, "5")
    with Session(engine) as db:
        other = create_queue_ticket(db, TicketCreate(institute_id=institute, service_id=care, idempotency_key="second-invoice")).id
        session = start_service_session(db, other, employee, care)
        finish_service_session(db, session.id)
    barrier = Barrier(2)
    def debit(db, key, target):
        cached = db.get(GiftCard, card)
        barrier.wait(timeout=10)
        result = tenders.allocate(db, institute, card, AllocationCreate(ticket_id=target, amount="5", idempotency_key=key), "operator")
        assert cached.remaining == 0
        return result
    results = race(engine, [lambda db: debit(db, "first", ticket), lambda db: debit(db, "second", other)])
    assert sorted(row[0] for row in results) == ["conflict", "ok"]
    with Session(engine) as db:
        assert db.get(GiftCard, card).remaining == 0
        assert len(db.scalars(select(GiftCardAllocation)).all()) == 1


def test_concurrent_replay_and_reversal_credit_only_once(postgres_flow, monkeypatch):
    engine, institute, employee, care = postgres_flow
    ticket, line, customers, package, member, card = setup(engine, institute, employee, care)
    intent = AllocationCreate(ticket_id=ticket, amount="5", idempotency_key="same-debit")
    results = race(engine, [lambda db: tenders.allocate(db, institute, card, intent, "operator")] * 2)
    assert results[0] == results[1] and results[0][0] == "ok"
    identifier = results[0][1]
    results = race(engine, [lambda db: tenders.reverse(db, institute, identifier, "Correction", "manager")] * 2)
    assert results == [("ok", identifier)] * 2
    with Session(engine) as db:
        assert db.get(GiftCard, card).remaining == 100
        tenders.allocate(db, institute, card, AllocationCreate(ticket_id=ticket, amount="5", idempotency_key="new-debit"), "operator")
        tenders.reverse(db, institute, identifier, "Correction", "manager")
        assert db.get(GiftCard, card).remaining == 95
    assert_downgrade_refused(engine, monkeypatch)


def test_reversal_and_closure_serialize_without_losing_credit(postgres_flow):
    engine, institute, employee, care = postgres_flow
    ticket, line, customers, package, member, card = setup(engine, institute, employee, care)
    with Session(engine) as db:
        amount = db.get(TicketLine, line).total
        identifier = tenders.allocate(db, institute, card, AllocationCreate(ticket_id=ticket, amount=amount,
            idempotency_key="full"), "operator").id
    results = race(engine, [lambda db: tenders.reverse(db, institute, identifier, "Correction", "manager"),
                           lambda db: complete_payment(db, ticket, employee, "carte_cadeau", actor="operator")])
    assert sorted(row[0] for row in results) == ["conflict", "ok"]
    with Session(engine) as db:
        paid = db.get(QueueTicket, ticket).status == "paid"
        assert db.get(GiftCard, card).remaining == (100 - amount if paid else 100)
        assert (db.get(GiftTenderClosure, ticket) is not None) == paid
        assert (db.get(GiftCardAllocation, identifier).reversed_at is None) == paid


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
        command.stamp(config, "d7fa12cfe247")
        with pytest.raises(RuntimeError, match="cannot preserve"):
            command.downgrade(config, "c6e901bed136")
