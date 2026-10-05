import pytest
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.tickets.service import attach_checkout_customer
from app.modules.tickets.currency import confirm_currency
from app.modules.gift_cards.service import configure_currency
from app.modules.commerce.service import consume_package, reverse_package_consumption
from app.modules.commerce.schemas import PackageConsume
from app.modules.memberships.benefits import apply_benefit, reverse_benefit
from app.modules.memberships.schemas import BenefitApply
from app.modules.loyalty import service, redemption
from app.modules.loyalty.schemas import AdjustmentCreate, RewardCreate, RewardApply
from test_membership_benefits_8h import prepare
from test_ticket_workflow import _auth_headers, _bootstrap_reference_data


@pytest.mark.parametrize("kind", ["package", "member", "loyalty"])
def test_history_metadata_survives_reversal_and_beneficiary_change(client, kind):
    institute, employees, services = _bootstrap_reference_data(client)
    employee, care = employees[0]["id"], services[0]["id"]
    ticket, line, customers, package, member = prepare(main_module.engine, institute, employee, care)
    headers = _auth_headers(institute_id=institute)
    path = f"/api/v1/tickets/{ticket}/customer"
    initial = client.patch(path, headers=headers, json={"customer_id": customers[0]})
    assert initial.status_code == 200 and initial.json()["lines"][0]["commercial_history"] is False
    with Session(main_module.engine) as db:
        configure_currency(db, institute, "CHF", "manager")
        confirm_currency(db, ticket, "CHF", "Explicit invoice", "operator")
        if kind == "package":
            row = consume_package(db, institute, package, PackageConsume(ticket_line_id=line, idempotency_key="apply"), "operator")
            reverse_package_consumption(db, institute, row.id, "Correction", "manager")
        elif kind == "member":
            row = apply_benefit(db, institute, member, BenefitApply(ticket_line_id=line, idempotency_key="apply"), "operator")
            reverse_benefit(db, institute, row.id, "Correction", "manager")
        else:
            service.adjust(db, institute, customers[0], AdjustmentCreate(points=30, reason="Explicit credit", idempotency_key="credit"), "manager")
            reward = service.create_reward(db, institute, RewardCreate(name="Reward", service_id=care, points_cost=10,
                minimum_points=0, discount_amount="1", currency="CHF", idempotency_key="reward"), "manager")
            row = redemption.apply(db, institute, reward.id, RewardApply(ticket_line_id=line, idempotency_key="apply"), "operator")
            redemption.reverse(db, institute, row.id, "Correction", "manager")
    for identity in (customers[1], None, customers[1]):
        response = client.patch(path, headers=headers, json={"customer_id": identity})
        assert response.status_code == 200, response.text
        assert response.json()["customer_id"] == identity
        assert response.json()["lines"][0]["commercial_history"] is True
    assert client.patch(path, headers=_auth_headers(institute_id="foreign"), json={"customer_id": customers[1]}).status_code == 403


from test_postgres_scheduling_4d import postgres_flow


def test_postgres_history_union_survives_beneficiary_change(postgres_flow):
    from app.modules.tickets.routes import _read_ticket
    from app.modules.tickets.models import QueueTicket
    engine, institute, employee, care = postgres_flow
    ticket, line, customers, package, member = prepare(engine, institute, employee, care)
    with Session(engine) as db:
        row = consume_package(db, institute, package, PackageConsume(ticket_line_id=line, idempotency_key="apply"), "operator")
        reverse_package_consumption(db, institute, row.id, "Correction", "manager")
        attach_checkout_customer(db, ticket, customers[1])
        result = _read_ticket(db, db.get(QueueTicket, ticket))
        assert result.customer_id == customers[1]
        assert result.lines[0].commercial_history is True
