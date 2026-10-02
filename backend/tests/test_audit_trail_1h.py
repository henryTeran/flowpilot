import json
import logging

from fastapi.testclient import TestClient

from app.core.logging_config import JsonLogFormatter
from app.core.security import create_access_token


def _auth_headers(role: str = "accueil", institute_id: str | None = None) -> dict[str, str]:
    token = create_access_token(
        subject="audit-user",
        extra_claims={"role": role, "institute_id": institute_id},
    )
    return {"Authorization": f"Bearer {token}"}


def _bootstrap_reference_data(client: TestClient) -> tuple[str, str]:
    response = client.post("/api/v1/dev/init-demo-data")
    assert response.status_code == 200

    institute_id = client.get(
        "/api/v1/institutes",
        headers=_auth_headers(role="accueil", institute_id=None),
    ).json()[0]["id"]
    service_id = client.get("/api/v1/services/catalog").json()[0]["id"]
    return institute_id, service_id


def _create_ticket(client: TestClient, institute_id: str, service_id: str) -> dict:
    response = client.post(
        "/api/v1/tickets",
        json={"institute_id": institute_id, "service_id": service_id},
        headers=_auth_headers(role="accueil", institute_id=institute_id),
    )
    assert response.status_code == 200
    return response.json()


def test_ticket_cancel_emits_structured_audit_event(client: TestClient):
    records = []

    class Capture(logging.Handler):
        def emit(self, record):
            records.append(json.loads(JsonLogFormatter().format(record)))

    handler = Capture()
    audit_logger = logging.getLogger("app.audit")
    audit_logger.addHandler(handler)

    try:
        institute_id, service_id = _bootstrap_reference_data(client)
        ticket = _create_ticket(client, institute_id, service_id)

        response = client.patch(
            f"/api/v1/tickets/{ticket['id']}/cancel",
            headers=_auth_headers(role="accueil", institute_id=institute_id),
        )

        assert response.status_code == 200

        audit_event = next(
            record
            for record in records
            if record.get("audit_action") == "ticket.cancelled"
        )
        assert audit_event["message"] == "Audit event"
        assert audit_event["audit_target_type"] == "ticket"
        assert audit_event["audit_target_id"] == ticket["id"]
        assert audit_event["audit_actor_role"] == "accueil"
        assert audit_event["audit_institute_id"] == institute_id
        assert audit_event["request_id"]
    finally:
        audit_logger.removeHandler(handler)
