from datetime import timedelta
from threading import Barrier

from sqlalchemy import select
from sqlalchemy.orm import Session

import app.main as main_module
from app.modules.commerce.models import CustomerPackage, PackagePlan, PackageRedemption
from app.modules.commerce.service import consume_package, issue_package, package_view
from app.modules.commerce.schemas import PackageConsume, PackageIssue
from app.modules.planning.service import start_service_session, finish_service_session
from app.modules.tickets.models import TicketLine
from app.modules.tickets.schemas import TicketCreate
from app.modules.tickets.service import create_queue_ticket
from app.shared.time import utcnow
from test_postgres_scheduling_4d import postgres_flow, race
from test_ticket_workflow import _auth_headers, _bootstrap_reference_data


def test_package_checkout_scope_expiry_replay_and_balance(client, monkeypatch):
    institute, employees, services = _bootstrap_reference_data(client)
    operator = _auth_headers(institute_id=institute)
    manager = _auth_headers("responsable_institut", institute)
    prefix = f"/api/v1/commerce/institutes/{institute}"
    terms = {"name": "Cure 2 seances", "service_id": services[0]["id"], "sessions": 2, "valid_days": 30}
    assert client.post(prefix + "/package-plans", headers=operator, json=terms).status_code == 403
    assert client.post(prefix + "/package-plans", headers=manager, json={**terms, "sessions": True}).status_code == 422
    plan = client.post(prefix + "/package-plans", headers=manager, json=terms)
    assert plan.status_code == 200, plan.text
    issue = {"plan_id": plan.json()["id"], "customer_id": "client-a", "idempotency_key": "grant-intent"}
    package = client.post(prefix + "/packages", headers=manager, json=issue)
    assert package.status_code == 200, package.text
    assert client.post(prefix + "/packages", headers=manager, json=issue).json() == package.json()
    assert client.post(prefix + "/packages", headers=manager, json={**issue, "customer_id": "client-b"}).status_code == 400
    package_id = package.json()["id"]
    assert package.json()["remaining"] == 2
    ticket = client.post("/api/v1/tickets", headers=operator, json={"institute_id": institute,
        "service_id": services[0]["id"], "customer_id": "client-a"}).json()
    consume = prefix + f"/packages/{package_id}/consume"
    payload = {"ticket_line_id": ticket["lines"][0]["id"], "idempotency_key": "redeem-intent"}
    assert client.post(consume, headers=operator, json=payload).status_code == 400
    started = client.post("/api/v1/planning/sessions/start", headers=operator, json={"ticket_id": ticket["id"],
        "employee_id": employees[0]["id"], "service_id": services[0]["id"]})
    assert started.status_code == 200, started.text
    assert client.patch(f"/api/v1/planning/sessions/{started.json()['id']}/finish", headers=operator).status_code == 200
    assert client.post(consume, headers=_auth_headers(institute_id="foreign"), json=payload).status_code == 403
    with Session(main_module.engine) as db:
        row = db.get(CustomerPackage, package_id)
        expiry = row.expires_at
        row.expires_at = utcnow() - timedelta(seconds=1)
        row.issued_at = row.expires_at - timedelta(days=30)
        db.commit()
    assert client.post(consume, headers=operator, json=payload).status_code == 400
    with Session(main_module.engine) as db:
        row = db.get(CustomerPackage, package_id)
        assert row.consumed == 0
        row.expires_at = expiry
        db.commit()
    wrong_customer = client.post(prefix + "/packages", headers=manager,
        json={**issue, "customer_id": "other-client", "idempotency_key": "other-customer"}).json()
    assert client.post(prefix + f"/packages/{wrong_customer['id']}/consume", headers=operator, json=payload).status_code == 400
    from app.modules.commerce import service as commerce_service
    from app.shared.exceptions import business_error
    original = commerce_service.record_event
    def fail_after_flush(*args):
        original(*args)
        raise business_error("Injected redemption failure")
    with monkeypatch.context() as patch:
        patch.setattr(commerce_service, "record_event", fail_after_flush)
        assert client.post(consume, headers=operator, json=payload).status_code == 400
    with Session(main_module.engine) as db:
        assert db.get(CustomerPackage, package_id).consumed == 0
        assert db.get(TicketLine, payload["ticket_line_id"]).total > 0
        assert db.scalars(select(PackageRedemption)).all() == []
    used = client.post(consume, headers=operator, json=payload)
    assert used.status_code == 200, used.text
    assert client.post(consume, headers=operator, json=payload).json() == used.json()
    assert used.json()["original_total"] > 0 and used.json()["sessions"] == 1
    assert client.post(consume, headers=operator, json={**payload, "idempotency_key": "another-intent"}).status_code == 400
    assert client.patch(f"/api/v1/tickets/{ticket['id']}/cancel", headers=operator).status_code == 400
    assert client.post(f"/api/v1/dev/reset-demo?institute_id={institute}", headers=manager).status_code == 400
    viewed = client.get(prefix + "/packages?customer_id=client-a", headers=operator).json()
    assert viewed[0]["consumed"] == 1 and viewed[0]["usable_sessions"] == 1
    assert len(client.get(prefix + f"/packages/{package_id}/history", headers=operator).json()) == 1
    waiting = client.get(f"/api/v1/tickets/waiting?institute_id={institute}", headers=operator).json()
    priced = next(item for item in waiting if item["id"] == ticket["id"])
    assert priced["total_amount"] == priced["lines"][0]["total"] == 0
    paid = client.patch(f"/api/v1/tickets/{ticket['id']}/checkout/pay", headers=operator,
                        json={"employee_id": employees[0]["id"], "payment_method": "cb"})
    assert paid.status_code == 200 and paid.json()["total_amount"] == 0
    assert client.post(consume, headers=operator, json=payload).json() == used.json()


def test_package_expires_at_boundary_without_destroying_remaining_balance():
    now = utcnow()
    package = CustomerPackage(id="p", institute_id="i", plan_id="plan", customer_id="c", service_id="s",
        name="Cure", sessions=5, consumed=2, issued_at=now - timedelta(days=1), expires_at=now)
    assert package_view(package, now)["status"] == "expired"
    assert package_view(package, now)["remaining"] == 3
    assert package_view(package, now)["usable_sessions"] == 0
    assert package_view(package, now - timedelta(microseconds=1))["usable_sessions"] == 3


def test_two_checkouts_cannot_overdraw_last_package_session(postgres_flow):
    engine, institute, employee, service = postgres_flow
    with Session(engine) as db:
        plan = PackagePlan(id="race-plan", institute_id=institute, service_id=service, name="Last session", sessions=1, valid_days=30)
        db.add(plan)
        db.commit()
        package = issue_package(db, institute, PackageIssue(plan_id=plan.id, customer_id="race-client", idempotency_key="issue-race"), "actor")
        package_id = package.id
        lines = []
        for _ in range(2):
            ticket = create_queue_ticket(db, TicketCreate(institute_id=institute, service_id=service, customer_id="race-client"))
            session = start_service_session(db, ticket.id, employee, service)
            finish_service_session(db, session.id)
            lines.append(db.scalar(select(TicketLine.id).where(TicketLine.ticket_id == ticket.id)))
    cached_before_lock = Barrier(2)
    def consume_with_cached_balance(db, line):
        cached = db.get(CustomerPackage, package_id)
        assert cached.consumed == 0
        cached_before_lock.wait(timeout=10)
        return consume_package(db, institute, package_id,
            PackageConsume(ticket_line_id=line, idempotency_key=f"consume-{line}"), "actor")
    actions = [lambda db, line=line: consume_with_cached_balance(db, line) for line in lines]
    assert sorted(status for status, _ in race(engine, actions)) == ["conflict", "ok"]
    with Session(engine) as db:
        assert db.get(CustomerPackage, package_id).consumed == 1
        assert len(db.scalars(select(PackageRedemption)).all()) == 1
        assert sum(line.total == 0 for line in db.scalars(select(TicketLine))) == 1
