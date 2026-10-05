from datetime import timedelta
from sqlalchemy import select
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.customers.models import Customer
from app.modules.institutes.models import Institute
from app.shared.time import utcnow
from test_ticket_workflow import _auth_headers, _bootstrap_reference_data


def test_customer_search_replay_and_registered_beneficiary_scope(client):
    institute, employees, services = _bootstrap_reference_data(client)
    operator = _auth_headers(institute_id=institute)
    prefix = f"/api/v1/customers/institutes/{institute}"
    data = {"display_name": "Émilie Dupont", "phone": "+41 79 123 45 67", "idempotency_key": "client-intent"}
    assert client.post(prefix, headers=_auth_headers(institute_id="foreign"), json=data).status_code == 403
    assert client.get(prefix, headers=_auth_headers("collaboratrice", institute)).status_code == 403
    created = client.post(prefix, headers=operator, json=data)
    assert created.status_code == 200, created.text
    customer = created.json()
    assert client.get(prefix + f"/{customer['id']}", headers=operator).json() == customer
    assert client.post(prefix, headers=operator, json=data).json() == customer
    assert client.post(prefix, headers=operator, json={**data, "display_name": "Different"}).status_code == 400
    assert client.get(prefix + "?q=emilie", headers=operator).json() == [customer]
    assert client.get(prefix + "?q=79123", headers=operator).json() == [customer]
    assert client.get(prefix + "?q=%25", headers=operator).json() == []
    assert client.get(prefix, headers=operator).json() == []
    unknown = "customer_missing"
    ticket_payload = {"institute_id": institute, "service_id": services[0]["id"], "customer_id": unknown}
    assert client.post("/api/v1/tickets", headers=operator, json=ticket_payload).status_code == 404
    ticket = client.post("/api/v1/tickets", headers=operator, json={**ticket_payload, "customer_id": customer["id"]})
    assert ticket.status_code == 200 and ticket.json()["customer_id"] == customer["id"]
    with Session(main_module.engine) as db:
        assert len(db.scalars(select(Customer)).all()) == 1
        row = db.get(Customer, customer["id"])
        assert row.created_by == "test-user"
        origin = db.get(Institute, institute)
        db.add(Institute(id="foreign", region_id=origin.region_id, name="Foreign", city="Test"))
        db.flush()
        row.institute_id = "foreign"
        db.commit()
    assert client.post("/api/v1/tickets", headers=operator, json={**ticket_payload, "customer_id": customer["id"]}).status_code == 404
    assert client.get(prefix + f"/{customer['id']}", headers=operator).status_code == 404


def test_booking_carries_selected_customer_to_checkout_and_rejects_unknown_binding(client):
    institute, employees, services = _bootstrap_reference_data(client)
    operator = _auth_headers(institute_id=institute)
    customer = client.post(f"/api/v1/customers/institutes/{institute}", headers=operator,
        json={"display_name": "Selected client", "idempotency_key": "booking-client"}).json()
    payload = {"institute_id": institute, "service_id": services[0]["id"], "employee_id": employees[0]["id"],
        "customer_name": customer["display_name"], "customer_id": customer["id"],
        "start_time": (utcnow() + timedelta(minutes=1)).isoformat(), "idempotency_key": "selected-booking"}
    assert client.post("/api/v1/appointments", headers=operator, json={**payload, "customer_id": "customer_missing"}).status_code == 404
    booking = client.post("/api/v1/appointments", headers=operator, json=payload)
    assert booking.status_code == 200, booking.text
    assert client.post("/api/v1/appointments", headers=operator, json=payload).json() == booking.json()
    path = f"/api/v1/appointments/{booking.json()['id']}"
    assert client.patch(path, headers=operator, json={"customer_id": "customer_missing"}).status_code == 404
    assert client.patch(path + "/start", headers=operator).status_code == 200
    finished = client.patch(path + "/complete", headers=operator).json()
    tickets = client.get(f"/api/v1/tickets/waiting?institute_id={institute}", headers=operator).json()
    checkout = next(item for item in tickets if item["id"] == finished["checkout_ticket_id"])
    assert checkout["customer_id"] == customer["id"]
    manager = _auth_headers("responsable_institut", institute)
    prefix = f"/api/v1/commerce/institutes/{institute}"
    plan = client.post(prefix + "/package-plans", headers=manager, json={"name": "Selected client cure",
        "service_id": services[0]["id"], "sessions": 2, "valid_days": 30}).json()
    package = client.post(prefix + "/packages", headers=manager, json={"plan_id": plan["id"],
        "customer_id": customer["id"], "idempotency_key": "selected-cure"}).json()
    covered = client.post(prefix + f"/packages/{package['id']}/consume", headers=operator,
        json={"ticket_line_id": checkout["lines"][0]["id"], "idempotency_key": "selected-session"})
    assert covered.status_code == 200, covered.text
