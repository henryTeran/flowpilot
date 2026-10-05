from datetime import timedelta
from pathlib import Path
from threading import Barrier
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select, text
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.memberships import benefits, service
from app.modules.memberships.models import MembershipBenefit, CustomerMembership
from app.modules.memberships.schemas import BenefitApply, MembershipIssue, PlanCreate
from app.modules.commerce.models import CustomerPackage
from app.modules.commerce.schemas import PackageConsume
from app.modules.commerce.service import consume_package
from app.modules.services.models import Service
from app.modules.tickets.models import QueueTicket, TicketLine
from app.modules.realtime.models import PlanningRevision
from app.modules.tickets.service import attach_checkout_customer, complete_payment
from app.shared.exceptions import business_error
from test_checkout_customer_8e import prepare as prepare_checkout
from test_postgres_scheduling_4d import postgres_flow, race
from test_ticket_workflow import _auth_headers, _bootstrap_reference_data


def prepare(engine, institute, employee, care):
    ticket, line, customers, package = prepare_checkout(engine, institute, employee, care)
    with Session(engine) as db:
        attach_checkout_customer(db, ticket, customers[0])
        plan = service.create_plan(db, institute, PlanCreate(name="Member", valid_days=30, idempotency_key="benefit-plan"), "manager")
        membership = service.issue_membership(db, institute, MembershipIssue(plan_id=plan.id,
            customer_id=customers[0], idempotency_key="benefit-issue"), "manager")
        return ticket, line, customers, package, membership.id


def test_member_pricing_scope_replay_expiry_restore_and_coverage_guards(client, monkeypatch):
    institute, employees, services = _bootstrap_reference_data(client)
    employee, care = employees[0]["id"], services[0]["id"]
    ticket, line, customers, package, membership = prepare(main_module.engine, institute, employee, care)
    operator, manager = _auth_headers(institute_id=institute), _auth_headers("responsable_institut", institute)
    prefix = f"/api/v1/memberships/institutes/{institute}"
    path = prefix + f"/{membership}/benefits"
    payload = {"ticket_line_id": line, "idempotency_key": "member-price"}
    assert client.post(path, headers=_auth_headers("accueil", "foreign"), json=payload).status_code == 403
    assert client.post(path, headers=_auth_headers("collaboratrice", institute), json=payload).status_code == 403
    with Session(main_module.engine) as db:
        unit = float(db.get(TicketLine, line).unit_price)
        member_unit = float(db.get(Service, care).price_member)
        db.get(TicketLine, line).quantity = 2
        db.get(TicketLine, line).total = unit * 2
        db.get(QueueTicket, ticket).total_amount = unit * 2
        db.commit()
        expiry = service.aware(db.get(CustomerMembership, membership).active_until)
    with monkeypatch.context() as patch:
        patch.setattr(benefits, "utcnow", lambda: expiry)
        assert client.post(path, headers=operator, json=payload).status_code == 400
    applied = client.post(path, headers=operator, json=payload)
    assert applied.status_code == 200, applied.text
    fact = applied.json()
    assert fact["quantity"] == 2 and fact["member_total"] == member_unit * 2
    assert fact["original_total"] == unit * 2 and fact["actor_id"] == "test-user"
    assert client.post(path, headers=operator, json=payload).json() == fact
    assert client.post(path, headers=operator, json={**payload, "ticket_line_id": "other"}).status_code == 400
    assert client.post(path, headers=operator, json={**payload, "idempotency_key": "second-price"}).status_code == 400
    assert client.patch(f"/api/v1/tickets/{ticket}/customer", headers=operator, json={"customer_id": customers[1]}).status_code == 400
    assert client.patch(f"/api/v1/tickets/{ticket}/cancel", headers=operator).status_code == 400
    assert client.patch(f"/api/v1/tickets/{ticket}/checkout/lines/{line}/remove", headers=operator).status_code == 400
    assert client.post(f"/api/v1/dev/reset-demo?institute_id={institute}", headers=manager).status_code == 400
    package_path = f"/api/v1/commerce/institutes/{institute}/packages/{package}/consume"
    assert client.post(package_path, headers=operator, json={"ticket_line_id": line, "idempotency_key": "stacked"}).status_code == 400
    with Session(main_module.engine) as db:
        assert float(db.get(QueueTicket, ticket).total_amount) == member_unit * 2
        db.get(Service, care).price_member = 1
        db.commit()
    assert client.post(path, headers=operator, json=payload).json() == fact
    reverse_path = prefix + f"/benefits/{fact['id']}/reverse"
    reason = {"reason": "Mauvais avantage"}
    assert client.post(reverse_path, headers=operator, json=reason).status_code == 403
    reversed_fact = client.post(reverse_path, headers=manager, json=reason)
    assert reversed_fact.status_code == 200, reversed_fact.text
    assert client.post(reverse_path, headers=manager, json=reason).json() == reversed_fact.json()
    assert client.post(reverse_path, headers=manager, json={"reason": "Other"}).status_code == 400
    assert client.post(path, headers=operator, json=payload).json() == reversed_fact.json()
    with Session(main_module.engine) as db:
        assert float(db.get(TicketLine, line).total) == float(db.get(QueueTicket, ticket).total_amount) == unit * 2
    assert client.patch(f"/api/v1/tickets/{ticket}/checkout/lines/{line}/remove", headers=operator).status_code == 400
    assert client.patch(f"/api/v1/tickets/{ticket}/customer", headers=operator, json={"customer_id": customers[1]}).status_code == 200
    assert client.post(path, headers=operator, json={**payload, "idempotency_key": "wrong-client"}).status_code == 400
    assert client.patch(f"/api/v1/tickets/{ticket}/customer", headers=operator, json={"customer_id": customers[0]}).status_code == 200
    covered = client.post(package_path, headers=operator, json={"ticket_line_id": line, "idempotency_key": "cure-after-reversal"})
    assert covered.status_code == 200, covered.text
    assert client.post(reverse_path, headers=manager, json=reason).json() == reversed_fact.json()
    with Session(main_module.engine) as db:
        assert float(db.get(QueueTicket, ticket).total_amount) == float(db.get(TicketLine, line).total) == 0
    assert client.post(path, headers=operator, json={**payload, "idempotency_key": "member-after-cure"}).status_code == 400
    assert len(client.get(path, headers=operator).json()) == 1
    assert_downgrade_retains_benefits(main_module.engine, monkeypatch)


def test_failed_apply_and_reverse_roll_back_all_prices_and_history(client, monkeypatch):
    institute, employees, services = _bootstrap_reference_data(client)
    ticket, line, customers, package, membership = prepare(main_module.engine, institute, employees[0]["id"], services[0]["id"])
    operator, manager = _auth_headers(institute_id=institute), _auth_headers("responsable_institut", institute)
    prefix = f"/api/v1/memberships/institutes/{institute}"
    path = prefix + f"/{membership}/benefits"
    payload = {"ticket_line_id": line, "idempotency_key": "atomic-benefit"}
    with Session(main_module.engine) as db:
        price = float(db.get(TicketLine, line).total)
        revision = db.get(PlanningRevision, institute).revision
    original = benefits.record_event
    def fail(*args):
        original(*args)
        raise business_error("Injected failure after price/history flush")
    with monkeypatch.context() as patch:
        patch.setattr(benefits, "record_event", fail)
        assert client.post(path, headers=operator, json=payload).status_code == 400
    with Session(main_module.engine) as db:
        assert len(db.scalars(select(MembershipBenefit)).all()) == 0
        assert float(db.get(TicketLine, line).total) == float(db.get(QueueTicket, ticket).total_amount) == price
        assert db.get(PlanningRevision, institute).revision == revision
    applied = client.post(path, headers=operator, json=payload).json()
    with Session(main_module.engine) as db:
        applied_revision = db.get(PlanningRevision, institute).revision
        assert applied_revision > revision
    assert client.post(path, headers=operator, json=payload).json() == applied
    reverse_path = prefix + f"/benefits/{applied['id']}/reverse"
    with monkeypatch.context() as patch:
        patch.setattr(benefits, "record_event", fail)
        assert client.post(reverse_path, headers=manager, json={"reason": "Correction"}).status_code == 400
    with Session(main_module.engine) as db:
        assert db.get(MembershipBenefit, applied["id"]).reversed_at is None
        assert float(db.get(TicketLine, line).total) == float(db.get(QueueTicket, ticket).total_amount) == applied["member_total"]
        assert db.get(PlanningRevision, institute).revision == applied_revision
        complete_payment(db, ticket, employees[0]["id"], "cb")
    assert client.post(reverse_path, headers=manager, json={"reason": "Correction"}).status_code == 400
    assert client.post(path, headers=operator, json=payload).json() == applied


@pytest.mark.parametrize("opponent", ["package", "payment", "customer"])
def test_benefit_competition_preserves_one_pricing_truth(postgres_flow, opponent):
    engine, institute, employee, care = postgres_flow
    ticket, line, customers, package, membership = prepare(engine, institute, employee, care)
    def apply(db):
        return benefits.apply_benefit(db, institute, membership, BenefitApply(ticket_line_id=line, idempotency_key="race-benefit"), "operator")
    def other(db):
        if opponent == "package":
            return consume_package(db, institute, package, PackageConsume(ticket_line_id=line, idempotency_key="race-cure"), "operator")
        if opponent == "payment":
            return complete_payment(db, ticket, employee, "cb")
        return attach_checkout_customer(db, ticket, customers[1])
    results = race(engine, [apply, other])
    if opponent != "payment":
        assert sorted(status for status, _ in results) == ["conflict", "ok"]
    else:
        assert results[1][0] == "ok"
    with Session(engine) as db:
        fact = db.scalar(select(MembershipBenefit))
        active = db.get(QueueTicket, ticket)
        amount = float(db.get(TicketLine, line).total)
        assert float(active.total_amount) == amount
        assert (fact is not None) == (results[0][0] == "ok")
        if fact:
            assert amount == float(fact.member_total) and active.customer_id == customers[0]
        if opponent == "package":
            assert (db.get(CustomerPackage, package).consumed == 1) == (fact is None)
            assert amount == (float(fact.member_total) if fact else 0)


def test_duplicate_reverse_and_payment_preserve_final_price(postgres_flow, monkeypatch):
    engine, institute, employee, care = postgres_flow
    ticket, line, customers, package, membership = prepare(engine, institute, employee, care)
    with Session(engine) as db:
        fact = benefits.apply_benefit(db, institute, membership, BenefitApply(ticket_line_id=line, idempotency_key="reverse-race"), "operator")
        identifier, original_price = fact.id, float(fact.original_total)
    preloaded = Barrier(2)
    def reverse(db):
        db.get(MembershipBenefit, identifier)
        preloaded.wait(timeout=10)
        return benefits.reverse_benefit(db, institute, identifier, "Correction", "manager")
    results = race(engine, [reverse, reverse])
    assert results == [("ok", identifier), ("ok", identifier)]
    with Session(engine) as db:
        assert float(db.get(QueueTicket, ticket).total_amount) == original_price
        new = benefits.apply_benefit(db, institute, membership, BenefitApply(ticket_line_id=line, idempotency_key="new-benefit"), "operator")
        new_id, member_price = new.id, float(new.member_total)
    results = race(engine, [lambda db: benefits.reverse_benefit(db, institute, new_id, "Correction", "manager"),
                           lambda db: complete_payment(db, ticket, employee, "cb")])
    assert results[1][0] == "ok"
    with Session(engine) as db:
        paid = db.get(QueueTicket, ticket)
        assert paid.status == "paid" and float(paid.total_amount) == float(db.get(TicketLine, line).total)
        assert float(paid.total_amount) == (original_price if results[0][0] == "ok" else member_price)
    assert_downgrade_retains_benefits(engine, monkeypatch)


def assert_downgrade_retains_benefits(engine, monkeypatch):
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
        command.stamp(config, "a4c789fcb914")
        with pytest.raises(RuntimeError, match="cannot preserve"):
            command.downgrade(config, "f3b678eba803")
