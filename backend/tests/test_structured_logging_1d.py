import json
import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.errors import configure_exception_handlers
from app.core.http import configure_http_middleware
from app.core.logging_config import JsonLogFormatter


@pytest.fixture
def structured_logs():
    records = []

    class Capture(logging.Handler):
        def emit(self, record):
            records.append(json.loads(JsonLogFormatter().format(record)))

    handler = Capture()
    app_logger = logging.getLogger("app")
    app_logger.addHandler(handler)
    try:
        yield records
    finally:
        app_logger.removeHandler(handler)


def _request_log(records):
    return next(record for record in records if record["message"] == "HTTP request completed")


def test_request_log_is_structured_and_correlated(client, structured_logs):
    response = client.get("/health?ignored=secret-query")

    assert response.status_code == 200
    record = _request_log(structured_logs)
    assert record["timestamp"]
    assert record["level"] == "INFO"
    assert record["logger"] == "app.core.http"
    assert record["request_id"] == response.headers["X-Request-ID"]
    assert record["method"] == "GET"
    assert record["path"] == "/health"
    assert record["status_code"] == 200
    assert record["duration_ms"] >= 0
    assert "secret-query" not in json.dumps(structured_logs)


def test_supplied_request_id_and_authorization_are_handled_safely(client, structured_logs):
    response = client.get(
        "/api/v1/tickets/waiting?institute_id=demo-institute-geneve",
        headers={"X-Request-ID": "upstream-1d-123", "Authorization": "Bearer do-not-log-this"},
    )

    assert response.status_code == 403
    assert response.headers["X-Request-ID"] == "upstream-1d-123"
    assert response.json()["error"]["request_id"] == "upstream-1d-123"
    record = _request_log(structured_logs)
    assert record["request_id"] == "upstream-1d-123"
    assert record["method"] == "GET"
    assert record["status_code"] == 403
    assert "do-not-log-this" not in json.dumps(structured_logs)


def test_application_log_inherits_request_context(structured_logs):
    app = FastAPI()
    configure_http_middleware(app)

    @app.get("/context")
    def context():
        logging.getLogger("app.phase1d").info("Safe application event")
        return {"ok": True}

    with TestClient(app) as client:
        response = client.get("/context", headers={"X-Request-ID": "context-1d-123"})

    assert response.status_code == 200
    event = next(record for record in structured_logs
                 if record["message"] == "Safe application event")
    assert event["request_id"] == "context-1d-123"


def test_unhandled_error_log_uses_same_request_id_without_exception_value(structured_logs):
    app = FastAPI()
    configure_http_middleware(app)
    configure_exception_handlers(app)

    @app.get("/failure")
    def failure():
        raise RuntimeError("private-error-value")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/failure", headers={"X-Request-ID": "failure-1d-123"})

    assert response.status_code == 500
    assert response.json()["error"]["request_id"] == "failure-1d-123"
    error_record = next(record for record in structured_logs
                        if record["message"] == "Unhandled application error")
    assert error_record["request_id"] == "failure-1d-123"
    assert _request_log(structured_logs)["status_code"] == 500
    assert "private-error-value" not in json.dumps(structured_logs)
