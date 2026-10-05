from datetime import timedelta

from sqlalchemy.orm import Session

import app.main as main_module
from app.modules.appointments.models import Appointment
from app.modules.planning.models import ServiceSession
from app.modules.tickets.models import QueueEvent
from app.shared.time import utcnow
from test_ticket_workflow import _auth_headers, _bootstrap_reference_data, _create_ticket


def test_extension_conflict_is_atomic_and_boundary_is_allowed(client):
    institute, employees, services = _bootstrap_reference_data(client)
    headers = _auth_headers(institute_id=institute)
    ticket = _create_ticket(client, institute, services[0]["id"])
    started = client.post("/api/v1/planning/sessions/start", headers=headers, json={
        "ticket_id": ticket["id"], "employee_id": employees[0]["id"], "service_id": services[0]["id"],
    })
    assert started.status_code == 200
    session_id = started.json()["id"]
    with Session(main_module.engine) as db:
        session = db.get(ServiceSession, session_id)
        start = utcnow() + timedelta(minutes=60)
        session.planned_end_time = start - timedelta(minutes=5)
        db.add(Appointment(id="extension-conflict", institute_id=institute,
                           employee_id=employees[0]["id"], service_id=services[0]["id"],
                           customer_name="Test", start_time=start, end_time=start + timedelta(minutes=30),
                           status="confirmed"))
        db.commit()
    path = f"/api/v1/planning/sessions/{session_id}/extend"
    allowed = client.patch(path, headers=headers, json={"minutes": 5, "idempotency_key": "first"})
    assert allowed.status_code == 200
    blocked = client.patch(path, headers=headers, json={"minutes": 5, "idempotency_key": "second"})
    assert blocked.status_code == 400
    with Session(main_module.engine) as db:
        session = db.get(ServiceSession, session_id)
        assert session.planned_end_time.isoformat() == start.replace(tzinfo=None).isoformat()
        assert session.duration_minutes == started.json()["duration_minutes"] + 5
        assert db.query(QueueEvent).filter_by(ticket_id=ticket["id"], event_type="queue.service_extended").count() == 1
        db.get(Appointment, "extension-conflict").status = "cancelled"
        db.commit()
    assert client.patch(path, headers=headers, json={"minutes": 5, "idempotency_key": "second"}).status_code == 200
