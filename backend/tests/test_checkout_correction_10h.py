"""Historical execution provenance must coexist with unpaid billing corrections."""
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.modules.tickets.models import TicketLine
from app.modules.tickets.schemas import TicketCreate
from app.modules.tickets.service import create_queue_ticket, remove_checkout_ticket_line, _ticket_lines
from app.modules.planning.service import start_service_session, finish_service_session
from app.modules.inventory.models import StockServiceBasis
from test_postgres_scheduling_4d import postgres_flow


def test_postgres_started_nonrepresentative_line_can_be_removed_from_invoice(postgres_flow):
    engine, institute, employee, service = postgres_flow
    with Session(engine) as db:
        ticket = create_queue_ticket(db, TicketCreate(institute_id=institute, service_ids=[service, service]))
        execution = start_service_session(db, ticket.id, employee, actor_id="signed-operator")
        finish_service_session(db, execution.id)
        bases = list(db.scalars(select(StockServiceBasis).where(StockServiceBasis.session_id == execution.id)))
        assert len(bases) == 2
        removed = next(row for row in bases if row.ticket_line_id != execution.ticket_line_id)
        line_id = removed.ticket_line_id
        original = (removed.id, removed.quantity, removed.state, removed.recipe_id)
        remove_checkout_ticket_line(db, ticket.id, line_id, "signed-operator")
        assert len(_ticket_lines(db, ticket.id)) == 1
        db.refresh(removed)
        assert (removed.id, removed.quantity, removed.state, removed.recipe_id) == original
        assert db.get(TicketLine, line_id) is not None


import pytest
from decimal import Decimal
from fastapi import HTTPException
import app.main as main_module
from app.core.security import create_access_token
from app.modules.tickets.models import QueueTicket
from app.modules.tickets.currency import confirm_currency
from app.modules.gift_cards.service import configure_currency
from app.modules.payments.quotes import authorization_amount
from app.modules.gift_cards.tenders import tender_view
from app.modules.memberships.benefits import checkout_line
from app.modules.planning.models import ServiceSession
from app.modules.inventory import consumptions, service as stock
from app.modules.inventory.schemas import ItemCreate, MovementCreate, ConsumptionCreate
from app.modules.inventory.models import StockConsumption
from test_inventory_10a import item, movement
from test_ticket_workflow import _bootstrap_reference_data, _auth_headers
from test_postgres_scheduling_4d import race


def completed(db, institute, employee, service):
    ticket = create_queue_ticket(db, TicketCreate(institute_id=institute, service_ids=[service, service]))
    execution = start_service_session(db, ticket.id, employee, actor_id="signed-operator")
    finish_service_session(db, execution.id)
    return ticket.id, execution.id


def test_http_representative_removal_preserves_stock_and_excludes_invoice_and_report(client):
    institute, employees, services = _bootstrap_reference_data(client)
    operator = _auth_headers(institute_id=institute)
    with Session(main_module.engine) as db:
        ticket, execution = completed(db, institute, employees[0]["id"], services[0]["id"])
        identifier = db.get(ServiceSession, execution).ticket_line_id
        line = db.get(TicketLine, identifier)
        terms = (line.quantity, line.unit_price, line.total, line.performed_by_employee_id)
        due = Decimal(str(line.total))
        basis = db.scalar(select(StockServiceBasis).where(StockServiceBasis.ticket_line_id == identifier))
        article = stock.create_item(db, institute, ItemCreate(**item()), "manager")
        stock.move(db, institute, article.id, MovementCreate(**movement()), "manager")
        actual = consumptions.create(db, institute, basis.id, ConsumptionCreate(entries=[dict(item_id=article.id, quantity="1.125")], reason="Actually used before correction", idempotency_key="measured"), "manager")
        original = actual.model_dump(mode="json")
        actual_id, stock_id = actual.id, article.id
        configure_currency(db, institute, "CHF", "manager")
        confirm_currency(db, ticket, "CHF", "Explicit invoice currency", "test-user")
    path = f"/api/v1/tickets/{ticket}/checkout/lines/{identifier}/remove"
    for headers in (_auth_headers("collaboratrice", institute), _auth_headers(institute_id="foreign"), _auth_headers(institute_id=None)):
        assert client.patch(path, headers=headers).status_code == 403
    first = client.patch(path, headers=operator)
    assert first.status_code == 200
    corrected = first.json()
    assert len(corrected["lines"]) == len(corrected["removed_lines"]) == 1
    removed = corrected["removed_lines"][0]
    assert removed["id"] == identifier and removed["invoice_removed_by_actor"] == "test-user"
    assert removed["invoice_removal_reason"] == "not_performed" and removed["invoice_removed_at"].endswith(("Z", "+00:00"))
    assert Decimal(str(corrected["total_amount"])) == due
    assert client.patch(path, headers=operator).json() == corrected
    other = {"Authorization": "Bearer " + create_access_token(subject="another", extra_claims={"role": "accueil", "institute_id": institute})}
    assert client.patch(path, headers=other).status_code == 400
    last = corrected["lines"][0]["id"]
    assert client.patch(f"/api/v1/tickets/{ticket}/checkout/lines/{last}/remove", headers=operator).status_code == 400
    with Session(main_module.engine) as db:
        line = db.get(TicketLine, identifier)
        assert (line.quantity, line.unit_price, line.total, line.performed_by_employee_id) == terms
        row = db.get(QueueTicket, ticket)
        assert authorization_amount(db, row).amount == due
        assert tender_view(db, row)["total"] == due
        with pytest.raises(HTTPException):
            checkout_line(db, institute, identifier)
        db.rollback()
        assert consumptions.snapshot(db, db.get(StockConsumption, actual_id)).model_dump(mode="json") == original
        assert stock.balance_milli(db, institute, stock_id) == 9000
        assert len(list(db.scalars(select(StockServiceBasis).where(StockServiceBasis.session_id == execution)))) == 2
    paid = client.patch(f"/api/v1/tickets/{ticket}/checkout/pay", headers=operator, json={"employee_id": employees[0]["id"], "payment_method": "especes"})
    assert paid.status_code == 200 and paid.json()["total_amount"] == float(due)
    assert client.patch(path, headers=operator).json()["removed_lines"][0] == removed
    report = client.get(f"/api/v1/tickets/chiffres?institute_id={institute}", headers=_auth_headers("responsable_institut", institute)).json()
    assert report["totals"]["prestations"] == 1
    assert Decimal(report["totals"]["total"]) == due


def test_postgres_competing_signed_removals_have_one_original_actor(postgres_flow):
    engine, institute, employee, service = postgres_flow
    with Session(engine) as db:
        ticket, execution = completed(db, institute, employee, service)
        identifier = _ticket_lines(db, ticket)[0].id
    outcomes = race(engine, [lambda db: remove_checkout_ticket_line(db, ticket, identifier, "actor-a"), lambda db: remove_checkout_ticket_line(db, ticket, identifier, "actor-b")])
    assert sorted(row[0] for row in outcomes) == ["conflict", "ok"]
    with Session(engine) as db:
        assert db.get(TicketLine, identifier).invoice_removed_by_actor in {"actor-a", "actor-b"}
        assert len(_ticket_lines(db, ticket)) == 1
        assert len(list(db.scalars(select(StockServiceBasis).where(StockServiceBasis.session_id == execution)))) == 2


def test_removed_line_is_excluded_from_paid_loyalty_basis(client):
    from test_loyalty_earning_8r import setup, payload
    from app.modules.loyalty import earning
    from app.modules.loyalty.models import LoyaltyEarning
    from app.modules.loyalty.schemas import EarningPolicyCreate
    from app.modules.tickets.service import add_checkout_ticket_line, complete_payment
    institute, employees, services = _bootstrap_reference_data(client)
    employee, care = employees[0]["id"], services[0]["id"]
    ticket, original_line, customer = setup(main_module.engine, institute, employee, care)
    with Session(main_module.engine) as db:
        earning.create_policy(db, institute, EarningPolicyCreate(**payload()), "manager")
        add_checkout_ticket_line(db, ticket, care)
        removed = next(line for line in _ticket_lines(db, ticket) if line.id != original_line)
        assert removed.total > 0
        remove_checkout_ticket_line(db, ticket, removed.id, "operator")
        complete_payment(db, ticket, employee, "especes", actor="operator", operator_institute=institute)
        fact = db.get(LoyaltyEarning, ticket)
        assert fact.basis_amount == Decimal("10.35")
        assert fact.points == 15


def test_postgres_preloaded_line_cannot_overwrite_another_signed_removal(postgres_flow):
    engine, institute, employee, service = postgres_flow
    with Session(engine) as db:
        ticket, _ = completed(db, institute, employee, service)
        identifier = _ticket_lines(db, ticket)[0].id
    with Session(engine) as stale:
        cached = stale.get(TicketLine, identifier)
        assert cached.invoice_removed_at is None
        with Session(engine) as writer:
            remove_checkout_ticket_line(writer, ticket, identifier, "first-actor")
            original_time = writer.get(TicketLine, identifier).invoice_removed_at
        with pytest.raises(HTTPException):
            remove_checkout_ticket_line(stale, ticket, identifier, "stale-actor")
        stale.rollback()
        assert cached.invoice_removed_at == original_time
        assert cached.invoice_removed_by_actor == "first-actor"
