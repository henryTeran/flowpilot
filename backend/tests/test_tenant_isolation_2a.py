from datetime import timedelta

from app.core.security import create_access_token
from app.shared.time import utcnow


def _auth_headers(role: str = "accueil", institute_id: str | None = None) -> dict[str, str]:
    token = create_access_token(
        subject="tenant-test-user",
        extra_claims={"role": role, "institute_id": institute_id},
    )
    return {"Authorization": f"Bearer {token}"}


def _bootstrap_reference_data(client) -> tuple[str, str, str]:
    response = client.post("/api/v1/dev/init-demo-data")
    assert response.status_code == 200

    institute_id = client.get(
        "/api/v1/institutes",
        headers=_auth_headers(role="accueil", institute_id=None),
    ).json()[0]["id"]
    employee_id = client.get(
        f"/api/v1/employees?institute_id={institute_id}",
        headers=_auth_headers(role="accueil", institute_id=institute_id),
    ).json()[0]["id"]
    service_id = client.get("/api/v1/services/catalog").json()[0]["id"]
    return institute_id, employee_id, service_id


def test_appointments_list_requires_auth(client):
    institute_id, _, _ = _bootstrap_reference_data(client)

    response = client.get(f"/api/v1/appointments?institute_id={institute_id}")

    assert response.status_code == 403


def test_appointment_actions_block_cross_institute_access(client):
    institute_id, employee_id, service_id = _bootstrap_reference_data(client)

    start_time = utcnow() + timedelta(minutes=20)
    create_response = client.post(
        "/api/v1/appointments",
        json={
            "institute_id": institute_id,
            "service_id": service_id,
            "employee_id": employee_id,
            "customer_name": "Cliente Test",
            "start_time": start_time.isoformat(),
        },
        headers=_auth_headers(role="accueil", institute_id=institute_id),
    )
    assert create_response.status_code == 200
    appointment_id = create_response.json()["id"]

    blocked_response = client.patch(
        f"/api/v1/appointments/{appointment_id}/cancel",
        headers=_auth_headers(role="accueil", institute_id=f"other-{institute_id}"),
    )

    assert blocked_response.status_code == 403


def test_dashboard_live_blocks_cross_institute_access(client):
    institute_id, _, _ = _bootstrap_reference_data(client)

    blocked_response = client.get(
        f"/api/v1/dashboard/institutes/{institute_id}/live",
        headers=_auth_headers(role="accueil", institute_id=f"other-{institute_id}"),
    )
    assert blocked_response.status_code == 403

    allowed_response = client.get(
        f"/api/v1/dashboard/institutes/{institute_id}/live",
        headers=_auth_headers(role="accueil", institute_id=institute_id),
    )
    assert allowed_response.status_code == 200


def test_employee_status_update_blocks_cross_institute_access(client):
    institute_id, employee_id, _ = _bootstrap_reference_data(client)

    blocked_response = client.patch(
        f"/api/v1/employees/{employee_id}/status",
        json={"status": "pause"},
        headers=_auth_headers(role="accueil", institute_id=f"other-{institute_id}"),
    )

    assert blocked_response.status_code == 403


def test_institutes_list_is_scoped_by_token_institute(client):
    institute_id, _, _ = _bootstrap_reference_data(client)

    scoped_response = client.get(
        "/api/v1/institutes",
        headers=_auth_headers(role="accueil", institute_id=institute_id),
    )

    assert scoped_response.status_code == 200
    scoped_payload = scoped_response.json()
    assert len(scoped_payload) == 1
    assert scoped_payload[0]["id"] == institute_id


def test_institute_detail_blocks_cross_institute_access(client):
    institute_id, _, _ = _bootstrap_reference_data(client)

    blocked_response = client.get(
        f"/api/v1/institutes/{institute_id}",
        headers=_auth_headers(role="accueil", institute_id=f"other-{institute_id}"),
    )
    assert blocked_response.status_code == 403

    allowed_response = client.get(
        f"/api/v1/institutes/{institute_id}",
        headers=_auth_headers(role="accueil", institute_id=institute_id),
    )
    assert allowed_response.status_code == 200
    assert allowed_response.json()["id"] == institute_id


def test_ticket_assign_blocks_cross_institute_access(client):
    institute_id, employee_id, service_id = _bootstrap_reference_data(client)

    ticket_response = client.post(
        "/api/v1/tickets",
        json={"institute_id": institute_id, "service_id": service_id},
        headers=_auth_headers(role="accueil", institute_id=institute_id),
    )
    assert ticket_response.status_code == 200
    ticket_id = ticket_response.json()["id"]

    blocked_response = client.patch(
        f"/api/v1/tickets/{ticket_id}/assign",
        json={"employee_id": employee_id},
        headers=_auth_headers(role="accueil", institute_id=f"other-{institute_id}"),
    )
    assert blocked_response.status_code == 403


def test_planning_start_blocks_cross_institute_access(client):
    institute_id, employee_id, service_id = _bootstrap_reference_data(client)

    ticket_response = client.post(
        "/api/v1/tickets",
        json={"institute_id": institute_id, "service_id": service_id},
        headers=_auth_headers(role="accueil", institute_id=institute_id),
    )
    assert ticket_response.status_code == 200
    ticket_id = ticket_response.json()["id"]

    blocked_response = client.post(
        "/api/v1/planning/sessions/start",
        json={"ticket_id": ticket_id, "employee_id": employee_id, "service_id": service_id},
        headers=_auth_headers(role="accueil", institute_id=f"other-{institute_id}"),
    )
    assert blocked_response.status_code == 403


def test_planning_finish_blocks_cross_institute_access(client):
    institute_id, employee_id, service_id = _bootstrap_reference_data(client)

    ticket_response = client.post(
        "/api/v1/tickets",
        json={"institute_id": institute_id, "service_id": service_id},
        headers=_auth_headers(role="accueil", institute_id=institute_id),
    )
    assert ticket_response.status_code == 200
    ticket_id = ticket_response.json()["id"]

    start_response = client.post(
        "/api/v1/planning/sessions/start",
        json={"ticket_id": ticket_id, "employee_id": employee_id, "service_id": service_id},
        headers=_auth_headers(role="accueil", institute_id=institute_id),
    )
    assert start_response.status_code == 200
    session_id = start_response.json()["id"]

    blocked_response = client.patch(
        f"/api/v1/planning/sessions/{session_id}/finish",
        headers=_auth_headers(role="accueil", institute_id=f"other-{institute_id}"),
    )
    assert blocked_response.status_code == 403
