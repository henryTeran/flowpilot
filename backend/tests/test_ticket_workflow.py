from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import app.main as main_module
from app.core.security import create_access_token
from app.modules.appointments.models import Appointment
from app.modules.planning.models import ServiceSession
from app.shared.ids import new_id
from app.shared.time import utcnow


def _auth_headers(role: str = "accueil", institute_id: str | None = None) -> dict[str, str]:
    token = create_access_token(
        subject="test-user",
        extra_claims={"role": role, "institute_id": institute_id},
    )
    return {"Authorization": f"Bearer {token}"}


def _unauthorized_headers(institute_id: str | None = None) -> dict[str, str]:
    return _auth_headers(role="collaboratrice", institute_id=institute_id)


def _wrong_institute_headers(institute_id: str) -> dict[str, str]:
    return _auth_headers(role="accueil", institute_id=f"other-{institute_id}")


def _bootstrap_reference_data(client: TestClient) -> tuple[str, list[dict], list[dict]]:
    response = client.post("/api/v1/dev/init-demo-data")
    assert response.status_code == 200

    institutes = client.get("/api/v1/institutes").json()
    institute_id = institutes[0]["id"]
    employees = client.get(f"/api/v1/employees?institute_id={institute_id}").json()
    services = client.get("/api/v1/services/catalog").json()
    return institute_id, employees, services


def _create_ticket(client: TestClient, institute_id: str, service_id: str) -> dict:
    response = client.post(
        "/api/v1/tickets",
        json={"institute_id": institute_id, "service_id": service_id},
        headers=_auth_headers(role="accueil", institute_id=institute_id),
    )
    assert response.status_code == 200
    return response.json()


def test_create_ticket_success(client: TestClient):
    institute_id, _, services = _bootstrap_reference_data(client)
    service_id = services[0]["id"]

    ticket = _create_ticket(client, institute_id, service_id)

    assert ticket["status"] == "waiting"
    assert ticket["institute_id"] == institute_id
    assert ticket["lines"]


def test_create_empty_ticket_rejected(client: TestClient):
    institute_id, _, _ = _bootstrap_reference_data(client)

    response = client.post(
        "/api/v1/tickets",
        json={"institute_id": institute_id},
        headers=_auth_headers(role="accueil", institute_id=institute_id),
    )

    assert response.status_code == 422


def test_assign_ticket_success(client: TestClient):
    institute_id, employees, services = _bootstrap_reference_data(client)
    service_id = services[0]["id"]
    employee_id = employees[0]["id"]

    ticket = _create_ticket(client, institute_id, service_id)
    response = client.patch(
        f"/api/v1/tickets/{ticket['id']}/assign",
        json={"employee_id": employee_id},
        headers=_auth_headers(role="accueil", institute_id=institute_id),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "assigned"
    assert payload["assigned_employee_id"] == employee_id


def test_assign_unavailable_employee_rejected(client: TestClient):
    institute_id, employees, services = _bootstrap_reference_data(client)
    service_id = services[0]["id"]
    employee_id = employees[0]["id"]

    pause_response = client.patch(
        f"/api/v1/employees/{employee_id}/status",
        json={"status": "pause"},
        headers=_auth_headers(role="accueil", institute_id=institute_id),
    )
    assert pause_response.status_code == 200

    ticket = _create_ticket(client, institute_id, service_id)
    response = client.patch(
        f"/api/v1/tickets/{ticket['id']}/assign",
        json={"employee_id": employee_id},
        headers=_auth_headers(role="accueil", institute_id=institute_id),
    )

    assert response.status_code == 400


def test_create_ticket_replay_with_same_idempotency_key_returns_same_ticket(client: TestClient):
    institute_id, _, services = _bootstrap_reference_data(client)
    service_id = services[0]["id"]
    idempotency_key = "ticket-replay-123"

    first = client.post(
        "/api/v1/tickets",
        json={"institute_id": institute_id, "service_id": service_id, "idempotency_key": idempotency_key},
        headers=_auth_headers(role="accueil", institute_id=institute_id),
    )
    second = client.post(
        "/api/v1/tickets",
        json={"institute_id": institute_id, "service_id": service_id, "idempotency_key": idempotency_key},
        headers=_auth_headers(role="accueil", institute_id=institute_id),
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]


def test_create_ticket_with_different_idempotency_keys_creates_distinct_tickets(client: TestClient):
    institute_id, _, services = _bootstrap_reference_data(client)
    service_id = services[0]["id"]

    first = client.post(
        "/api/v1/tickets",
        json={"institute_id": institute_id, "service_id": service_id, "idempotency_key": "ticket-a"},
        headers=_auth_headers(role="accueil", institute_id=institute_id),
    )
    second = client.post(
        "/api/v1/tickets",
        json={"institute_id": institute_id, "service_id": service_id, "idempotency_key": "ticket-b"},
        headers=_auth_headers(role="accueil", institute_id=institute_id),
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] != second.json()["id"]


def test_ticket_create_requires_ticket_manager_role(client: TestClient):
    institute_id, _, services = _bootstrap_reference_data(client)
    service_id = services[0]["id"]

    response = client.post(
        "/api/v1/tickets",
        json={"institute_id": institute_id, "service_id": service_id},
        headers=_unauthorized_headers(institute_id),
    )

    assert response.status_code == 403


def test_ticket_create_rejects_wrong_institute(client: TestClient):
    institute_id, _, services = _bootstrap_reference_data(client)
    service_id = services[0]["id"]

    response = client.post(
        "/api/v1/tickets",
        json={"institute_id": institute_id, "service_id": service_id},
        headers=_wrong_institute_headers(institute_id),
    )

    assert response.status_code == 403


def test_ticket_assign_allows_accueil_role(client: TestClient):
    institute_id, employees, services = _bootstrap_reference_data(client)
    service_id = services[0]["id"]
    employee_id = employees[0]["id"]

    ticket = _create_ticket(client, institute_id, service_id)
    response = client.patch(
        f"/api/v1/tickets/{ticket['id']}/assign",
        json={"employee_id": employee_id},
        headers=_auth_headers(role="accueil", institute_id=institute_id),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "assigned"


def test_ticket_assign_rejects_unauthorized_role(client: TestClient):
    institute_id, employees, services = _bootstrap_reference_data(client)
    service_id = services[0]["id"]
    employee_id = employees[0]["id"]

    ticket = _create_ticket(client, institute_id, service_id)
    response = client.patch(
        f"/api/v1/tickets/{ticket['id']}/assign",
        json={"employee_id": employee_id},
        headers=_unauthorized_headers(institute_id),
    )

    assert response.status_code == 403


def test_assign_ticket_rejected_when_employee_has_active_delayed_session(client: TestClient):
    institute_id, employees, services = _bootstrap_reference_data(client)
    service_id = services[0]["id"]
    employee_id = employees[0]["id"]

    first_ticket = _create_ticket(client, institute_id, service_id)
    start_response = client.post(
        "/api/v1/planning/sessions/start",
        json={"ticket_id": first_ticket["id"], "employee_id": employee_id, "service_id": service_id},
        headers=_auth_headers(role="accueil", institute_id=institute_id),
    )
    assert start_response.status_code == 200

    with Session(main_module.engine) as db:
        session = db.query(ServiceSession).filter_by(employee_id=employee_id).first()
        assert session is not None
        session.status = "delayed"
        session.planned_end_time = session.start_time - timedelta(minutes=5)
        db.add(session)
        db.commit()

    second_ticket = _create_ticket(client, institute_id, service_id)
    response = client.patch(
        f"/api/v1/tickets/{second_ticket['id']}/assign",
        json={"employee_id": employee_id},
        headers=_auth_headers(role="accueil", institute_id=institute_id),
    )

    assert response.status_code == 400


def test_assign_ticket_rejected_when_employee_has_active_appointment(client: TestClient):
    institute_id, employees, services = _bootstrap_reference_data(client)
    service_id = services[0]["id"]
    employee_id = employees[0]["id"]

    appointment = Appointment(
        id=new_id("apt"),
        institute_id=institute_id,
        service_id=service_id,
        employee_id=employee_id,
        customer_name="Client test",
        phone=None,
        start_time=utcnow() - timedelta(minutes=15),
        end_time=utcnow() + timedelta(minutes=30),
        status="in_progress",
    )

    with Session(main_module.engine) as db:
        db.add(appointment)
        db.commit()

    ticket = _create_ticket(client, institute_id, service_id)
    response = client.patch(
        f"/api/v1/tickets/{ticket['id']}/assign",
        json={"employee_id": employee_id},
        headers=_auth_headers(role="accueil", institute_id=institute_id),
    )

    assert response.status_code == 400


def test_planning_start_rejects_unauthorized_role(client: TestClient):
    institute_id, employees, services = _bootstrap_reference_data(client)
    service_id = services[0]["id"]
    employee_id = employees[0]["id"]
    ticket = _create_ticket(client, institute_id, service_id)

    response = client.post(
        "/api/v1/planning/sessions/start",
        json={"ticket_id": ticket["id"], "employee_id": employee_id, "service_id": service_id},
        headers=_unauthorized_headers(institute_id),
    )

    assert response.status_code == 403
