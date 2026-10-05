from datetime import timedelta

import pytest
from sqlalchemy.orm import Session

import app.main as main_module
from app.modules.appointments.models import Appointment
from app.modules.planning.models import ServiceSession
from app.shared.time import utcnow
from test_ticket_workflow import _auth_headers, _bootstrap_reference_data, _create_ticket


@pytest.mark.parametrize("blocker", ["session", "appointment"])
def test_overdue_occupancy_blocks_future_booking_until_finished(client, blocker):
    institute, employees, services = _bootstrap_reference_data(client)
    headers = _auth_headers(institute_id=institute)
    payload = {"institute_id": institute, "employee_id": employees[0]["id"],
               "service_id": services[0]["id"], "customer_name": "Test",
               "start_time": (utcnow() + timedelta(minutes=1)).isoformat()}
    future = client.post("/api/v1/appointments", headers=headers,
                         json={**payload, "start_time": (utcnow() + timedelta(hours=3)).isoformat()})
    assert future.status_code == 200
    move_path = f"/api/v1/appointments/{future.json()['id']}"
    move = {"start_time": (utcnow() + timedelta(hours=4)).isoformat()}
    if blocker == "session":
        ticket = _create_ticket(client, institute, services[0]["id"])
        started = client.post("/api/v1/planning/sessions/start", headers=headers,
                              json={"ticket_id": ticket["id"], "employee_id": employees[0]["id"], "service_id": services[0]["id"]})
        assert started.status_code == 200
        identifier = started.json()["id"]
        with Session(main_module.engine) as db:
            db.get(ServiceSession, identifier).start_time = utcnow() - timedelta(minutes=30)
            db.get(ServiceSession, identifier).planned_end_time = utcnow() - timedelta(minutes=1)
            db.commit()
        finish_path = f"/api/v1/planning/sessions/{identifier}/finish"
    else:
        booked = client.post("/api/v1/appointments", headers=headers, json=payload)
        assert booked.status_code == 200
        identifier = booked.json()["id"]
        assert client.patch(f"/api/v1/appointments/{identifier}/start", headers=headers).status_code == 200
        with Session(main_module.engine) as db:
            db.get(Appointment, identifier).start_time = utcnow() - timedelta(minutes=30)
            db.get(Appointment, identifier).end_time = utcnow() - timedelta(minutes=1)
            db.commit()
        finish_path = f"/api/v1/appointments/{identifier}/complete"
    payload["start_time"] = (utcnow() + timedelta(hours=2)).isoformat()
    assert client.post("/api/v1/appointments", headers=headers, json=payload).status_code == 400
    assert client.patch(move_path, headers=headers, json=move).status_code == 400
    assert client.patch(finish_path, headers=headers).status_code == 200
    assert client.post("/api/v1/appointments", headers=headers, json=payload).status_code == 200
    assert client.patch(move_path, headers=headers, json=move).status_code == 200
