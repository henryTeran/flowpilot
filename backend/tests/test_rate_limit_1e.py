import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.http import auth_rate_limiter


def _seed_and_get_login(client: TestClient) -> dict[str, str]:
    response = client.post("/api/v1/dev/init-demo-data")
    assert response.status_code == 200
    payload = response.json()["data"]
    return {"email": payload["login"], "password": payload["password"]}


@pytest.fixture(autouse=True)
def reset_rate_limiter_state() -> None:
    auth_rate_limiter.reset()


def test_login_rate_limit_returns_standardized_429(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    credentials = _seed_and_get_login(client)

    monkeypatch.setattr(settings, "ENABLE_RATE_LIMITING", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_AUTH_MAX_REQUESTS", 2)
    monkeypatch.setattr(settings, "RATE_LIMIT_AUTH_WINDOW_SECONDS", 60)

    first = client.post(
        "/api/v1/auth/login",
        json={"email": credentials["email"], "password": "wrong-password"},
        headers={"X-Forwarded-For": "203.0.113.42"},
    )
    second = client.post(
        "/api/v1/auth/login",
        json={"email": credentials["email"], "password": "wrong-password"},
        headers={"X-Forwarded-For": "203.0.113.42"},
    )
    limited = client.post(
        "/api/v1/auth/login",
        json={"email": credentials["email"], "password": "wrong-password"},
        headers={"X-Forwarded-For": "203.0.113.42"},
    )

    assert first.status_code == 401
    assert second.status_code == 401
    assert limited.status_code == 429
    payload = limited.json()
    assert payload["error"]["code"] == "rate_limit_exceeded"
    assert payload["error"]["request_id"]
    assert limited.headers["X-Request-ID"] == payload["error"]["request_id"]


def test_login_rate_limit_isolated_per_client_fingerprint(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    credentials = _seed_and_get_login(client)

    monkeypatch.setattr(settings, "ENABLE_RATE_LIMITING", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_AUTH_MAX_REQUESTS", 1)
    monkeypatch.setattr(settings, "RATE_LIMIT_AUTH_WINDOW_SECONDS", 60)

    first_ip_attempt = client.post(
        "/api/v1/auth/login",
        json={"email": credentials["email"], "password": "wrong-password"},
        headers={"X-Forwarded-For": "198.51.100.10"},
    )
    blocked_first_ip = client.post(
        "/api/v1/auth/login",
        json={"email": credentials["email"], "password": "wrong-password"},
        headers={"X-Forwarded-For": "198.51.100.10"},
    )
    second_ip_attempt = client.post(
        "/api/v1/auth/login",
        json={"email": credentials["email"], "password": "wrong-password"},
        headers={"X-Forwarded-For": "198.51.100.11"},
    )

    assert first_ip_attempt.status_code == 401
    assert blocked_first_ip.status_code == 429
    assert second_ip_attempt.status_code == 401
