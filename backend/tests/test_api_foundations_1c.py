from fastapi.testclient import TestClient

from app.core.security import create_access_token


def _auth_headers(role: str = "accueil", institute_id: str | None = None) -> dict[str, str]:
    token = create_access_token(
        subject="test-user",
        extra_claims={"role": role, "institute_id": institute_id},
    )
    return {"Authorization": f"Bearer {token}"}


def _bootstrap_reference_data(client: TestClient) -> str:
    response = client.post("/api/v1/dev/init-demo-data")
    assert response.status_code == 200

    institutes = client.get("/api/v1/institutes").json()
    return institutes[0]["id"]


def test_forbidden_error_is_standardized_and_has_request_id(client: TestClient):
    response = client.get("/api/v1/tickets/waiting?institute_id=demo-institute-geneve")

    assert response.status_code == 403
    payload = response.json()
    assert payload["error"]["code"] == "http_403"
    assert payload["error"]["message"] == "Token manquant"
    assert payload["error"]["request_id"]
    assert response.headers.get("X-Request-ID") == payload["error"]["request_id"]


def test_validation_error_format_is_predictable(client: TestClient):
    institute_id = _bootstrap_reference_data(client)

    response = client.post(
        "/api/v1/tickets",
        json={"institute_id": institute_id},
        headers=_auth_headers(role="accueil", institute_id=institute_id),
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["error"]["code"] == "validation_error"
    assert payload["error"]["message"] == "Validation error"
    assert payload["error"]["request_id"]
    assert isinstance(payload["error"]["details"], list)


def test_employees_pagination_defaults(client: TestClient):
    institute_id = _bootstrap_reference_data(client)

    response = client.get(
        f"/api/v1/employees?institute_id={institute_id}",
        headers=_auth_headers(role="accueil", institute_id=institute_id),
    )

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert len(payload) >= 1


def test_employees_pagination_limit_offset(client: TestClient):
    institute_id = _bootstrap_reference_data(client)

    headers = _auth_headers(role="accueil", institute_id=institute_id)
    first_page = client.get(f"/api/v1/employees?institute_id={institute_id}&limit=1&offset=0", headers=headers)
    second_page = client.get(f"/api/v1/employees?institute_id={institute_id}&limit=1&offset=1", headers=headers)

    assert first_page.status_code == 200
    assert second_page.status_code == 200

    first_payload = first_page.json()
    second_payload = second_page.json()

    assert len(first_payload) == 1
    assert len(second_payload) == 1
    assert first_payload[0]["id"] != second_payload[0]["id"]


def test_pagination_max_limit_validation(client: TestClient):
    response = client.get("/api/v1/institutes?limit=999")

    assert response.status_code == 422
    payload = response.json()
    assert payload["error"]["code"] == "validation_error"
    assert payload["error"]["request_id"]
