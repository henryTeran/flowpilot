from fastapi.testclient import TestClient

import app.main as main_module
from app.core.config import settings
from app.main import create_app


def test_ready_returns_ok_when_database_is_reachable(client: TestClient):
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_ready_returns_standardized_503_when_database_is_unavailable(monkeypatch):
    class BrokenEngine:
        def connect(self):
            raise RuntimeError("db down")

    monkeypatch.setattr(settings, "AUTO_CREATE_SCHEMA_ON_STARTUP", False)
    monkeypatch.setattr(main_module, "engine", BrokenEngine())

    app = create_app()
    with TestClient(app) as test_client:
        response = test_client.get("/ready")

    assert response.status_code == 503
    payload = response.json()
    assert payload["error"]["code"] == "service_unavailable"
    assert payload["error"]["message"] == "Database unavailable"
    assert payload["error"]["request_id"]
