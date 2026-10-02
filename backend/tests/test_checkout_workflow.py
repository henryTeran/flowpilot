from fastapi.testclient import TestClient

from app.core.security import create_access_token


def _auth_headers(role: str = "accueil", institute_id: str | None = None) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(subject='test-user', extra_claims={'role': role, 'institute_id': institute_id})}"}


def _unauthorized_headers(institute_id: str | None = None) -> dict[str, str]:
    return _auth_headers(role="collaboratrice", institute_id=institute_id)


def _wrong_institute_headers(institute_id: str) -> dict[str, str]:
    return _auth_headers(role="accueil", institute_id=f"other-{institute_id}")


def _bootstrap_reference_data(client: TestClient) -> tuple[str, list[dict], list[dict]]:
    response = client.post("/api/v1/dev/init-demo-data")
    assert response.status_code == 200

    institutes = client.get("/api/v1/institutes").json()
    institute_id = institutes[0]["id"]
    employees = client.get(
        f"/api/v1/employees?institute_id={institute_id}",
        headers=_auth_headers(role="accueil", institute_id=institute_id),
    ).json()
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


def _start_and_finish_ticket(client: TestClient, ticket_id: str, employee_id: str, service_id: str):
    start = client.post(
        "/api/v1/planning/sessions/start",
        json={
            "ticket_id": ticket_id,
            "employee_id": employee_id,
            "service_id": service_id,
        },
        headers=_auth_headers(role="accueil", institute_id=None),
    )
    assert start.status_code == 200
    session_id = start.json()["id"]

    finish = client.patch(
        f"/api/v1/planning/sessions/{session_id}/finish",
        headers=_auth_headers(role="accueil", institute_id=None),
    )
    assert finish.status_code == 200


def _start_checkout(client: TestClient, ticket_id: str, employee_id: str):
    return client.patch(
        f"/api/v1/tickets/{ticket_id}/checkout/start",
        json={"employee_id": employee_id},
        headers=_auth_headers(role="accueil", institute_id=None),
    )


def _pay(client: TestClient, ticket_id: str, employee_id: str, method: str = "cb"):
    return client.patch(
        f"/api/v1/tickets/{ticket_id}/checkout/pay",
        json={"employee_id": employee_id, "payment_method": method},
        headers=_auth_headers(role="accueil", institute_id=None),
    )


def test_start_checkout_success(client: TestClient):
    institute_id, employees, services = _bootstrap_reference_data(client)
    employee_id = employees[0]["id"]
    service_id = services[0]["id"]

    ticket = _create_ticket(client, institute_id, service_id)
    _start_and_finish_ticket(client, ticket["id"], employee_id, service_id)

    response = _start_checkout(client, ticket["id"], employee_id)

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "in_checkout"
    assert payload["checkout_employee_id"] == employee_id


def test_payment_success(client: TestClient):
    institute_id, employees, services = _bootstrap_reference_data(client)
    employee_id = employees[0]["id"]
    service_id = services[0]["id"]

    ticket = _create_ticket(client, institute_id, service_id)
    _start_and_finish_ticket(client, ticket["id"], employee_id, service_id)
    start_checkout = _start_checkout(client, ticket["id"], employee_id)
    assert start_checkout.status_code == 200

    payment = _pay(client, ticket["id"], employee_id, "cb")
    assert payment.status_code == 200
    assert payment.json()["status"] == "paid"


def test_payment_clears_stale_assignment_and_keeps_employee_available(client: TestClient):
    institute_id, employees, services = _bootstrap_reference_data(client)
    employee_id = employees[0]["id"]
    service_id = services[0]["id"]

    ticket = _create_ticket(client, institute_id, service_id)
    _start_and_finish_ticket(client, ticket["id"], employee_id, service_id)
    _start_checkout(client, ticket["id"], employee_id)

    payment = _pay(client, ticket["id"], employee_id, "cb")
    assert payment.status_code == 200
    payload = payment.json()

    assert payload["status"] == "paid"
    assert payload["assigned_employee_id"] is None

    refreshed_employee = client.get(
        f"/api/v1/employees?institute_id={institute_id}",
        headers=_auth_headers(role="accueil", institute_id=institute_id),
    ).json()
    employee = next(item for item in refreshed_employee if item["id"] == employee_id)
    assert employee["status"] == "available"


def test_double_payment_rejected(client: TestClient):
    institute_id, employees, services = _bootstrap_reference_data(client)
    employee_id = employees[0]["id"]
    service_id = services[0]["id"]

    ticket = _create_ticket(client, institute_id, service_id)
    _start_and_finish_ticket(client, ticket["id"], employee_id, service_id)
    _start_checkout(client, ticket["id"], employee_id)

    first = _pay(client, ticket["id"], employee_id, "cb")
    assert first.status_code == 200

    second = _pay(client, ticket["id"], employee_id, "cb")
    assert second.status_code == 400


def test_payment_before_checkout_state_rejected(client: TestClient):
    institute_id, employees, services = _bootstrap_reference_data(client)
    employee_id = employees[0]["id"]
    service_id = services[0]["id"]

    ticket = _create_ticket(client, institute_id, service_id)
    payment = _pay(client, ticket["id"], employee_id, "cb")

    assert payment.status_code == 400


def test_invalid_payment_method_rejected(client: TestClient):
    institute_id, employees, services = _bootstrap_reference_data(client)
    employee_id = employees[0]["id"]
    service_id = services[0]["id"]

    ticket = _create_ticket(client, institute_id, service_id)
    _start_and_finish_ticket(client, ticket["id"], employee_id, service_id)
    _start_checkout(client, ticket["id"], employee_id)

    payment = _pay(client, ticket["id"], employee_id, "bitcoin")
    assert payment.status_code == 400


def test_wrong_checkout_employee_rejected(client: TestClient):
    institute_id, employees, services = _bootstrap_reference_data(client)
    employee_a = employees[0]["id"]
    employee_b = employees[1]["id"]
    service_id = services[0]["id"]

    ticket = _create_ticket(client, institute_id, service_id)
    _start_and_finish_ticket(client, ticket["id"], employee_a, service_id)

    start = _start_checkout(client, ticket["id"], employee_a)
    assert start.status_code == 200

    wrong_payment = _pay(client, ticket["id"], employee_b, "cb")
    assert wrong_payment.status_code == 400


def test_paid_ticket_contributes_once_to_revenue(client: TestClient):
    institute_id, employees, services = _bootstrap_reference_data(client)
    employee_id = employees[0]["id"]
    service_id = services[0]["id"]

    ticket = _create_ticket(client, institute_id, service_id)
    _start_and_finish_ticket(client, ticket["id"], employee_id, service_id)
    _start_checkout(client, ticket["id"], employee_id)

    first_payment = _pay(client, ticket["id"], employee_id, "cb")
    assert first_payment.status_code == 200

    chiffres_before = client.get(
        f"/api/v1/tickets/chiffres?institute_id={institute_id}",
        headers=_auth_headers(role="accueil", institute_id=institute_id),
    )
    assert chiffres_before.status_code == 200
    total_before = chiffres_before.json()["totals"]["total"]

    replay_payment = _pay(client, ticket["id"], employee_id, "cb")
    assert replay_payment.status_code == 400

    chiffres_after = client.get(
        f"/api/v1/tickets/chiffres?institute_id={institute_id}",
        headers=_auth_headers(role="accueil", institute_id=institute_id),
    )
    assert chiffres_after.status_code == 200
    total_after = chiffres_after.json()["totals"]["total"]

    assert total_after == total_before
