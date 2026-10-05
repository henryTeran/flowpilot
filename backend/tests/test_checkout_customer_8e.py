from sqlalchemy import select
from sqlalchemy.orm import Session

import app.main as main_module
from app.modules.customers.schemas import CustomerCreate
from app.modules.customers.service import create_customer
from app.modules.commerce.models import CustomerPackage, PackagePlan
from app.modules.commerce.schemas import PackageConsume, PackageIssue
from app.modules.commerce.service import consume_package, issue_package, reverse_package_consumption
from app.modules.planning.service import start_service_session, finish_service_session
from app.modules.tickets.models import QueueTicket, TicketLine, QueueEvent
from app.modules.tickets.schemas import TicketCreate
from app.modules.tickets.service import attach_checkout_customer, create_queue_ticket, complete_payment
from test_postgres_scheduling_4d import postgres_flow, race
from test_ticket_workflow import _auth_headers, _bootstrap_reference_data


def prepare(engine, institute, employee, service):
    with Session(engine) as db:
        customers = [create_customer(db, institute, CustomerCreate(display_name=name, idempotency_key=name), "operator").id
                     for name in ("First client", "Second client")]
        ticket = create_queue_ticket(db, TicketCreate(institute_id=institute, service_id=service,
                                                     idempotency_key="anonymous-intent"))
        ticket_id = ticket.id
        session = start_service_session(db, ticket_id, employee, service)
        finish_service_session(db, session.id)
        line = db.scalar(select(TicketLine).where(TicketLine.ticket_id == ticket_id))
        line_id = line.id
        db.add(PackagePlan(id="attach-plan", institute_id=institute, service_id=service,
                           name="Cure", sessions=2, valid_days=30))
        db.commit()
        package = issue_package(db, institute, PackageIssue(plan_id="attach-plan", customer_id=customers[0],
                                                           idempotency_key="attach-issue"), "manager")
        return ticket_id, line_id, customers, package.id


def test_checkout_customer_scope_coverage_reversal_replay_and_paid_guards(client, monkeypatch):
    institute, employees, services = _bootstrap_reference_data(client)
    employee, service = employees[0]["id"], services[0]["id"]
    ticket, line, customers, package = prepare(main_module.engine, institute, employee, service)
    operator = _auth_headers(institute_id=institute)
    path = f"/api/v1/tickets/{ticket}/customer"
    def attach(customer, headers=operator):
        return client.patch(path, headers=headers, json={"customer_id": customer})
    assert attach(customers[0], _auth_headers(institute_id="foreign")).status_code == 403
    assert attach(customers[0], _auth_headers(institute_id=None)).status_code == 403
    assert attach(customers[0], _auth_headers("collaboratrice", institute)).status_code == 403
    assert attach("customer_missing").status_code == 404
    assert client.patch(path, headers=operator, json={}).status_code == 422
    waiting = client.post("/api/v1/tickets", headers=operator, json={"institute_id": institute,
        "service_id": service}).json()
    assert client.patch(f"/api/v1/tickets/{waiting['id']}/customer", headers=operator,
                        json={"customer_id": customers[0]}).status_code == 400
    from app.modules.tickets import service as ticket_service
    from app.shared.exceptions import business_error
    def fail(*args):
        raise business_error("Injected event failure")
    with monkeypatch.context() as patch:
        patch.setattr(ticket_service, "record_event", fail)
        assert attach(customers[0]).status_code == 400
    with Session(main_module.engine) as db:
        assert db.get(QueueTicket, ticket).customer_id is None
    assert attach(customers[0]).json()["customer_id"] == customers[0]
    assert attach(customers[0]).status_code == 200
    replay = client.post("/api/v1/tickets", headers=operator, json={"institute_id": institute,
        "service_id": service, "idempotency_key": "anonymous-intent"})
    assert replay.status_code == 200 and replay.json()["customer_id"] == customers[0]
    with Session(main_module.engine) as db:
        redemption = consume_package(db, institute, package,
            PackageConsume(ticket_line_id=line, idempotency_key="attach-consume"), "operator")
        redemption_id = redemption.id
    assert attach(customers[1]).status_code == 400
    assert attach(None).status_code == 400
    assert attach(customers[0]).status_code == 200
    with Session(main_module.engine) as db:
        reverse_package_consumption(db, institute, redemption_id, "Wrong beneficiary", "manager")
    assert attach(customers[1]).status_code == 200
    assert attach(None).json()["customer_id"] is None
    with Session(main_module.engine) as db:
        complete_payment(db, ticket, employee, "cb")
        assert len(db.scalars(select(QueueEvent).where(QueueEvent.ticket_id == ticket,
            QueueEvent.event_type == "queue.customer_changed")).all()) == 3
    assert attach(customers[0]).status_code == 400


def test_customer_change_and_consumption_cannot_mix_beneficiaries(postgres_flow):
    engine, institute, employee, service = postgres_flow
    ticket, line, customers, package = prepare(engine, institute, employee, service)
    with Session(engine) as db:
        attach_checkout_customer(db, ticket, customers[0])
    results = race(engine, [lambda db: attach_checkout_customer(db, ticket, customers[1]),
        lambda db: consume_package(db, institute, package,
            PackageConsume(ticket_line_id=line, idempotency_key="attach-race"), "operator")])
    assert sorted(status for status, _ in results) == ["conflict", "ok"]
    with Session(engine) as db:
        beneficiary = db.get(QueueTicket, ticket).customer_id
        consumed = db.get(CustomerPackage, package).consumed
        assert (beneficiary, consumed) in [(customers[0], 1), (customers[1], 0)]
        assert float(db.get(TicketLine, line).total) == (0 if consumed else float(db.get(QueueTicket, ticket).total_amount))


def test_customer_change_and_payment_preserve_final_identity(postgres_flow):
    engine, institute, employee, service = postgres_flow
    ticket, line, customers, package = prepare(engine, institute, employee, service)
    results = race(engine, [lambda db: attach_checkout_customer(db, ticket, customers[0]),
                           lambda db: complete_payment(db, ticket, employee, "cb")])
    assert results[1][0] == "ok"
    with Session(engine) as db:
        assert db.get(QueueTicket, ticket).status == "paid"
        assert db.get(QueueTicket, ticket).customer_id == (customers[0] if results[0][0] == "ok" else None)
