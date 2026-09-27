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


def _start_session(client: TestClient, ticket_id: str, employee_id: str, service_id: str):
    return client.post(
        "/api/v1/planning/sessions/start",
        json={
            "ticket_id": ticket_id,
            "employee_id": employee_id,
            "service_id": service_id,
        },
    )


def test_start_service_success(client: TestClient):
    institute_id, employees, services = _bootstrap_reference_data(client)
    employee_id = employees[0]["id"]
    service_id = services[0]["id"]

    ticket = _create_ticket(client, institute_id, service_id)

    response = _start_session(client, ticket["id"], employee_id, service_id)

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "in_progress"


def test_double_start_rejected(client: TestClient):
    institute_id, employees, services = _bootstrap_reference_data(client)
    employee_id = employees[0]["id"]
    service_id = services[0]["id"]

    ticket = _create_ticket(client, institute_id, service_id)
    first = _start_session(client, ticket["id"], employee_id, service_id)
    assert first.status_code == 200

    second = _start_session(client, ticket["id"], employee_id, service_id)
    assert second.status_code == 400


def test_start_invalid_ticket_state_rejected(client: TestClient):
    institute_id, employees, services = _bootstrap_reference_data(client)
    employee_id = employees[0]["id"]
    service_id = services[0]["id"]

    ticket = _create_ticket(client, institute_id, service_id)
    cancel_response = client.patch(f"/api/v1/tickets/{ticket['id']}/cancel")
    assert cancel_response.status_code == 200

    start = _start_session(client, ticket["id"], employee_id, service_id)
    assert start.status_code == 400


def test_start_unavailable_employee_rejected(client: TestClient):
    institute_id, employees, services = _bootstrap_reference_data(client)
    employee_id = employees[0]["id"]
    service_id = services[0]["id"]

    pause_response = client.patch(
        f"/api/v1/employees/{employee_id}/status",
        json={"status": "pause"},
    )
    assert pause_response.status_code == 200

    ticket = _create_ticket(client, institute_id, service_id)
    start = _start_session(client, ticket["id"], employee_id, service_id)
    assert start.status_code == 400


def test_finish_service_success(client: TestClient):
    institute_id, employees, services = _bootstrap_reference_data(client)
    employee_id = employees[0]["id"]
    service_id = services[0]["id"]

    ticket = _create_ticket(client, institute_id, service_id)
    started = _start_session(client, ticket["id"], employee_id, service_id)
    assert started.status_code == 200
    session_id = started.json()["id"]

    finished = client.patch(f"/api/v1/planning/sessions/{session_id}/finish")
    assert finished.status_code == 200
    assert finished.json()["status"] == "completed"

    tickets = client.get(f"/api/v1/tickets/waiting?institute_id={institute_id}").json()
    refreshed = next(item for item in tickets if item["id"] == ticket["id"])
    assert refreshed["status"] == "ready_for_checkout"


def test_double_finish_is_safe(client: TestClient):
    institute_id, employees, services = _bootstrap_reference_data(client)
    employee_id = employees[0]["id"]
    service_id = services[0]["id"]

    ticket = _create_ticket(client, institute_id, service_id)
    started = _start_session(client, ticket["id"], employee_id, service_id)
    session_id = started.json()["id"]

    first_finish = client.patch(f"/api/v1/planning/sessions/{session_id}/finish")
    assert first_finish.status_code == 200

    second_finish = client.patch(f"/api/v1/planning/sessions/{session_id}/finish")
    assert second_finish.status_code == 400


def test_finish_unknown_or_non_active_session_rejected(client: TestClient):
    _bootstrap_reference_data(client)

    response = client.patch("/api/v1/planning/sessions/sess-unknown/finish")
    assert response.status_code == 404
