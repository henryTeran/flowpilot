from fastapi import HTTPException
from decimal import Decimal
import pytest
from sqlalchemy import event, select
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.loyalty import service, redemption
from app.modules.loyalty.models import LoyaltyRedemption, LoyaltyEntry
from app.modules.gift_cards.schemas import GiftCardIssue, AllocationCreate
from app.modules.gift_cards.service import issue_card
from app.modules.gift_cards.tenders import allocate
from app.modules.loyalty.schemas import RewardCreate, RewardApply, AdjustmentCreate
from app.modules.tickets.models import QueueTicket, TicketLine
from app.modules.tickets.service import attach_checkout_customer, cancel_ticket, remove_checkout_ticket_line
from app.modules.commerce.service import consume_package
from app.modules.commerce.schemas import PackageConsume
from app.modules.memberships.benefits import apply_benefit
from app.modules.memberships.schemas import BenefitApply
from app.shared.exceptions import business_error
from test_loyalty_earning_8r import setup
from test_postgres_scheduling_4d import postgres_flow, race
from test_ticket_workflow import _auth_headers, _bootstrap_reference_data


def configure(engine, institute, care, customer, credit=30):
    with Session(engine) as db:
        service.adjust(db, institute, customer, AdjustmentCreate(points=credit, reason="Initial points", idempotency_key="initial"), "manager")
        return service.create_reward(db, institute, RewardCreate(name="Reward", service_id=care, points_cost=10,
            minimum_points=20, discount_amount="2.50", currency="CHF", idempotency_key="reward"), "manager").id


def test_reward_checkout_atomicity_replay_restore_and_guarded_history(client, monkeypatch):
    institute, employees, services = _bootstrap_reference_data(client)
    employee, care = employees[0]["id"], services[0]["id"]
    ticket, line, customer = setup(main_module.engine, institute, employee, care)
    reward = configure(main_module.engine, institute, care, customer)
    operator, manager = _auth_headers(institute_id=institute), _auth_headers("responsable_institut", institute)
    root = f"/api/v1/loyalty/institutes/{institute}"
    path, payload = root + f"/rewards/{reward}/apply", dict(ticket_line_id=line, idempotency_key="apply")
    for headers in (_auth_headers(institute_id=None), _auth_headers(institute_id="foreign"), _auth_headers("collaboratrice", institute)):
        assert client.post(path, headers=headers, json=payload).status_code == 403
    def fail(db, context, instances):
        if any(isinstance(row, LoyaltyRedemption) for row in db.new):
            raise business_error("Injected redemption failure")
    event.listen(Session, "before_flush", fail)
    try:
        assert client.post(path, headers=operator, json=payload).status_code == 400
    finally:
        event.remove(Session, "before_flush", fail)
    with Session(main_module.engine) as db:
        assert service.points(db, institute, customer) == 30
        assert db.get(TicketLine, line).total == Decimal("10.35")
    response = client.post(path, headers=operator, json=payload)
    assert response.status_code == 200, response.text
    fact = response.json()
    assert Decimal(fact["reward_total"]) == Decimal("7.85") and fact["points_cost"] == 10
    assert client.post(path, headers=operator, json=payload).json() == fact
    assert client.post(path, headers=operator, json={**payload, "idempotency_key": "second"}).status_code == 400
    with Session(main_module.engine) as db:
        assert service.points(db, institute, customer) == 20
        with pytest.raises(HTTPException):
            attach_checkout_customer(db, ticket, None)
        db.rollback()
        with pytest.raises(HTTPException):
            cancel_ticket(db, ticket)
        db.rollback()
    from app.modules.commerce.models import CustomerPackage
    from app.modules.memberships.models import CustomerMembership
    with Session(main_module.engine) as db:
        package, member = db.scalar(select(CustomerPackage)).id, db.scalar(select(CustomerMembership)).id
        with pytest.raises(HTTPException):
            consume_package(db, institute, package, PackageConsume(ticket_line_id=line, idempotency_key="package"), "operator")
        db.rollback()
        with pytest.raises(HTTPException):
            apply_benefit(db, institute, member, BenefitApply(ticket_line_id=line, idempotency_key="member"), "operator")
        db.rollback()
        assert service.points(db, institute, customer) == 20
    reverse = root + f"/redemptions/{fact['id']}/reverse"
    assert client.post(reverse, headers=operator, json={"reason": "Correction"}).status_code == 403
    def fail_reversal(db, context, instances):
        if any(isinstance(row, LoyaltyEntry) and row.points == 10 for row in db.new):
            raise business_error("Injected reversal failure")
    event.listen(Session, "before_flush", fail_reversal)
    try:
        assert client.post(reverse, headers=manager, json={"reason": "Correction"}).status_code == 400
    finally:
        event.remove(Session, "before_flush", fail_reversal)
    with Session(main_module.engine) as db:
        assert service.points(db, institute, customer) == 20
        assert db.get(TicketLine, line).total == Decimal("7.85")
    assert client.post(reverse, headers=manager, json={"reason": "Correction"}).status_code == 200
    assert client.post(reverse, headers=manager, json={"reason": "Another reason"}).status_code == 400
    with Session(main_module.engine) as db:
        assert service.points(db, institute, customer) == 30
        assert db.get(TicketLine, line).total == Decimal("10.35")
        with pytest.raises(HTTPException, match="historique"):
            remove_checkout_ticket_line(db, ticket, line)
        db.rollback()
    newer = client.post(path, headers=operator, json={**payload, "idempotency_key": "new"})
    assert newer.status_code == 200
    assert client.post(reverse, headers=manager, json={"reason": "Correction"}).status_code == 200
    with Session(main_module.engine) as db:
        assert service.points(db, institute, customer) == 20
        assert db.get(TicketLine, line).total == Decimal("7.85")
    from app.modules.loyalty.earning import create_policy
    from app.modules.loyalty.schemas import EarningPolicyCreate
    with Session(main_module.engine) as db:
        create_policy(db, institute, EarningPolicyCreate(currency="CHF", points_per_unit="1.5",
            enabled=True, reason="Explicit earning", idempotency_key="policy"), "manager")
    pay = f"/api/v1/tickets/{ticket}/checkout/pay"
    assert client.patch(pay, headers=operator, json=dict(employee_id=employee, payment_method="cb")).status_code == 200
    assert client.post(path, headers=operator, json={**payload, "idempotency_key": "new"}).status_code == 200
    assert client.post(root + f"/redemptions/{newer.json()['id']}/reverse", headers=manager, json={"reason": "Correction"}).status_code == 400
    with Session(main_module.engine) as db:
        assert service.points(db, institute, customer) == 31  # floor(7.85 * 1.5), after reward reduction.
    assert len(client.get(root + f"/customers/{customer}/redemptions", headers=operator).json()) == 2
    assert client.post(f"/api/v1/dev/reset-demo?institute_id={institute}").status_code == 400
    assert_downgrade_refused(main_module.engine, monkeypatch)


@pytest.mark.parametrize("quantity,credit,expected", [(2,30,10), (2,19,None), (4,30,None)])
def test_full_line_quantity_and_balance_threshold(client, quantity, credit, expected):
    institute, employees, services = _bootstrap_reference_data(client)
    care = services[0]["id"]
    ticket, line, customer = setup(main_module.engine, institute, employees[0]["id"], care)
    reward = configure(main_module.engine, institute, care, customer, credit)
    with Session(main_module.engine) as db:
        db.get(TicketLine, line).quantity = quantity
        db.get(TicketLine, line).total = Decimal("10.35") * quantity
        db.commit()
        if expected is None:
            with pytest.raises(HTTPException):
                redemption.apply(db, institute, reward, RewardApply(ticket_line_id=line, idempotency_key="apply"), "operator")
            db.rollback()
            assert service.points(db, institute, customer) == credit
        else:
            row = redemption.apply(db, institute, reward, RewardApply(ticket_line_id=line, idempotency_key="apply"), "operator")
            assert row.points_cost == 20 and row.reward_total == Decimal("15.70")
            assert service.points(db, institute, customer) == expected


def test_duplicate_redemption_and_reversal_serialize(postgres_flow):
    engine, institute, employee, care = postgres_flow
    ticket, line, customer = setup(engine, institute, employee, care)
    reward = configure(engine, institute, care, customer)
    payload = RewardApply(ticket_line_id=line, idempotency_key="apply")
    results = race(engine, [lambda db: redemption.apply(db, institute, reward, payload, "operator")] * 2)
    assert all(row[0] == "ok" for row in results) and results[0][1] == results[1][1]
    identifier = results[0][1]
    results = race(engine, [lambda db: redemption.reverse(db, institute, identifier, "Correction", "manager")] * 2)
    assert all(row[0] == "ok" for row in results)
    with Session(engine) as db:
        assert service.points(db, institute, customer) == 30
        assert [row.points for row in db.scalars(select(LoyaltyEntry).order_by(LoyaltyEntry.occurred_at))] == [30,-10,10]
        assert db.get(TicketLine, line).total == Decimal("10.35")


@pytest.mark.parametrize("coverage", ["package", "member", "gift", "currency", "service", "customer"])
def test_ineligible_and_covered_lines_cannot_spend_points(client, coverage):
    institute, employees, services = _bootstrap_reference_data(client)
    employee, care = employees[0]["id"], services[0]["id"]
    ticket, line, customer = setup(main_module.engine, institute, employee, care)
    reward = configure(main_module.engine, institute, care, customer)
    from app.modules.commerce.models import CustomerPackage
    from app.modules.memberships.models import CustomerMembership
    with Session(main_module.engine) as db:
        package = db.scalar(select(CustomerPackage)).id
        member = db.scalar(select(CustomerMembership)).id
        if coverage == "package":
            consume_package(db, institute, package, PackageConsume(ticket_line_id=line, idempotency_key="package"), "operator")
        elif coverage == "member":
            apply_benefit(db, institute, member, BenefitApply(ticket_line_id=line, idempotency_key="member"), "operator")
        elif coverage == "gift":
            card = issue_card(db, institute, GiftCardIssue(amount="20", reason="Gift credit", valid_days=30, idempotency_key="card"), "manager")
            allocate(db, institute, card.id, AllocationCreate(ticket_id=ticket, amount="1", idempotency_key="gift"), "operator")
        else:
            if coverage == "currency":
                db.get(QueueTicket, ticket).currency = None
            elif coverage == "service":
                db.get(TicketLine, line).service_id = services[1]["id"]
            else:
                db.get(QueueTicket, ticket).customer_id = None
            db.commit()
        with pytest.raises(HTTPException):
            redemption.apply(db, institute, reward, RewardApply(ticket_line_id=line, idempotency_key="apply"), "operator")
        db.rollback()
        assert service.points(db, institute, customer) == 30
        assert list(db.scalars(select(LoyaltyRedemption))) == []


def test_point_correction_and_reward_cannot_overdraw(postgres_flow):
    engine, institute, employee, care = postgres_flow
    ticket, line, customer = setup(engine, institute, employee, care)
    reward = configure(engine, institute, care, customer)
    results = race(engine, [lambda db: redemption.apply(db, institute, reward,
        RewardApply(ticket_line_id=line, idempotency_key="apply"), "operator"),
        lambda db: service.adjust(db, institute, customer,
        AdjustmentCreate(points=-25, reason="Correction", idempotency_key="correction"), "manager")])
    assert sorted(row[0] for row in results) == ["conflict", "ok"]
    with Session(engine) as db:
        assert service.points(db, institute, customer) in (5,20)



def assert_downgrade_refused(engine, monkeypatch):
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
        command.stamp(config, "1bde5603268b")
        with pytest.raises(RuntimeError, match="cannot preserve"):
            command.downgrade(config, "0acd45f2157a")
