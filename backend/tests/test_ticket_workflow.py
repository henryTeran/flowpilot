from fastapi.testclient import TestClient


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
    )
    assert pause_response.status_code == 200

    ticket = _create_ticket(client, institute_id, service_id)
    response = client.patch(
        f"/api/v1/tickets/{ticket['id']}/assign",
        json={"employee_id": employee_id},
    )

    assert response.status_code == 400


def test_create_ticket_replay_with_same_idempotency_key_returns_same_ticket(client: TestClient):
    institute_id, _, services = _bootstrap_reference_data(client)
    service_id = services[0]["id"]
    idempotency_key = "ticket-replay-123"

    first = client.post(
        "/api/v1/tickets",
        json={"institute_id": institute_id, "service_id": service_id, "idempotency_key": idempotency_key},
    )
    second = client.post(
        "/api/v1/tickets",
        json={"institute_id": institute_id, "service_id": service_id, "idempotency_key": idempotency_key},
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
    )
    second = client.post(
        "/api/v1/tickets",
        json={"institute_id": institute_id, "service_id": service_id, "idempotency_key": "ticket-b"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] != second.json()["id"]
