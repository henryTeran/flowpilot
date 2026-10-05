from datetime import datetime, timedelta

import pytest
from sqlalchemy import event
from sqlalchemy.orm import Session

import app.main as main_module
from app.modules.planning.models import ServiceSession, SessionExtension
from app.modules.tickets.models import QueueEvent
from test_ticket_workflow import _auth_headers, _bootstrap_reference_data, _create_ticket


@pytest.fixture
def extension_flow(client):
    institute, employees, services = _bootstrap_reference_data(client)
    headers = _auth_headers(institute_id=institute)
    ticket = _create_ticket(client, institute, services[0]["id"])
    response = client.post("/api/v1/planning/sessions/start", headers=headers, json={
        "ticket_id": ticket["id"], "employee_id": employees[0]["id"], "service_id": services[0]["id"],
    })
    assert response.status_code == 200
    return response.json(), ticket, headers


def test_extension_replay_applies_once_and_records_evidence(client, extension_flow):
    session, ticket, headers = extension_flow
    path = f"/api/v1/planning/sessions/{session['id']}/extend"
    payload = {"minutes": 10, "idempotency_key": "lost-response-retry"}
    first = client.patch(path, headers=headers, json=payload)
    retry = client.patch(path, headers=headers, json=payload)
    assert first.status_code == retry.status_code == 200
    assert first.json() == retry.json()
    assert first.json()["duration_minutes"] == session["duration_minutes"] + 10
    with Session(main_module.engine) as db:
        record = db.query(SessionExtension).one()
        assert record.institute_id == session["institute_id"]
        assert record.requested_by == "test-user"
        assert record.resulting_end_time - record.previous_end_time == timedelta(minutes=10)
        assert db.query(QueueEvent).filter_by(ticket_id=ticket["id"], event_type="queue.service_extended").count() == 1
    assert client.patch(path, headers=headers, json={**payload, "minutes": 5}).status_code == 400
    assert client.patch(path, headers=headers, json={"minutes": 5, "idempotency_key": "next-action"}).status_code == 200
    assert client.patch(f"/api/v1/planning/sessions/{session['id']}/finish", headers=headers).status_code == 200
    # A late retry after finish is still a replay, not another transition.
    assert client.patch(path, headers=headers, json=payload).status_code == 200
    with Session(main_module.engine) as db:
        assert db.get(ServiceSession, session["id"]).duration_minutes == session["duration_minutes"] + 15
        assert db.query(SessionExtension).count() == 2


@pytest.mark.parametrize("payload", [{"minutes": 10}, {"minutes": 10, "idempotency_key": ""},
                                     {"minutes": 10, "idempotency_key": " "},
                                     {"minutes": 10, "idempotency_key": "x" * 121}])
def test_extension_requires_valid_replay_key(client, extension_flow, payload):
    session, ticket, headers = extension_flow
    response = client.patch(f"/api/v1/planning/sessions/{session['id']}/extend", headers=headers, json=payload)
    assert response.status_code in {400, 422}
    with Session(main_module.engine) as db:
        assert db.get(ServiceSession, session["id"]).duration_minutes == session["duration_minutes"]
        assert db.query(SessionExtension).count() == 0


def test_extension_replay_is_still_authorized_and_tenant_scoped(client, extension_flow):
    session, ticket, headers = extension_flow
    path = f"/api/v1/planning/sessions/{session['id']}/extend"
    payload = {"minutes": 10, "idempotency_key": "authorization-replay"}
    assert client.patch(path, headers=headers, json=payload).status_code == 200
    assert client.patch(path, json=payload).status_code == 403
    assert client.patch(path, headers=_auth_headers("collaboratrice", session["institute_id"]), json=payload).status_code == 403
    assert client.patch(path, headers=_auth_headers(institute_id="other"), json=payload).status_code == 403


def test_failed_extension_record_insert_rolls_back_session_and_event(client, extension_flow):
    session, ticket, headers = extension_flow
    def fail_insert(mapper, connection, target):
        raise RuntimeError("injected persistence failure")
    event.listen(SessionExtension, "before_insert", fail_insert)
    try:
        with pytest.raises(RuntimeError, match="injected persistence failure"):
            client.patch(f"/api/v1/planning/sessions/{session['id']}/extend", headers=headers,
                         json={"minutes": 10, "idempotency_key": "atomic-write"})
    finally:
        event.remove(SessionExtension, "before_insert", fail_insert)
    with Session(main_module.engine) as db:
        assert db.get(ServiceSession, session["id"]).duration_minutes == session["duration_minutes"]
        assert db.query(SessionExtension).count() == 0
        assert db.query(QueueEvent).filter_by(ticket_id=ticket["id"], event_type="queue.service_extended").count() == 0
