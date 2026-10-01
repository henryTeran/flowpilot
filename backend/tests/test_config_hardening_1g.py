import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import create_app


@pytest.fixture(autouse=True)
def reset_security_settings(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "APP_ENV", "local")
    monkeypatch.setattr(settings, "APP_DEBUG", True)
    monkeypatch.setattr(settings, "SECRET_KEY", "change-me")
    monkeypatch.setattr(settings, "ENABLE_RATE_LIMITING", True)
    monkeypatch.setattr(settings, "CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")
    monkeypatch.setattr(settings, "AUTO_CREATE_SCHEMA_ON_STARTUP", False)


def test_production_rejects_weak_secret(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "APP_DEBUG", False)
    monkeypatch.setattr(settings, "SECRET_KEY", "change-me")
    monkeypatch.setattr(settings, "CORS_ORIGINS", "https://app.flowpilot.test")

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app()


def test_production_rejects_non_https_cors_origin(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "APP_DEBUG", False)
    monkeypatch.setattr(settings, "SECRET_KEY", "flowpilot-super-secret-key")
    monkeypatch.setattr(settings, "CORS_ORIGINS", "http://app.flowpilot.test")

    with pytest.raises(RuntimeError, match="HTTPS"):
        create_app()


def test_production_rejects_localhost_cors_origin(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "APP_DEBUG", False)
    monkeypatch.setattr(settings, "SECRET_KEY", "flowpilot-super-secret-key")
    monkeypatch.setattr(settings, "CORS_ORIGINS", "https://localhost")

    with pytest.raises(RuntimeError, match="Localhost"):
        create_app()


def test_production_accepts_secure_runtime_settings(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "APP_DEBUG", False)
    monkeypatch.setattr(settings, "SECRET_KEY", "flowpilot-super-secret-key")
    monkeypatch.setattr(settings, "CORS_ORIGINS", "https://app.flowpilot.test")

    app = create_app()
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
