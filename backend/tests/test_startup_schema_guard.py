import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import create_app


def test_production_blocks_auto_create_schema(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "AUTO_CREATE_SCHEMA_ON_STARTUP", True)

    with pytest.raises(RuntimeError, match="AUTO_CREATE_SCHEMA_ON_STARTUP"):
        with TestClient(create_app()):
            pass
