from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

import app.main as main_module
from app.modules.resources.models import ResourceReservation
from app.shared.time import utcnow
from test_ticket_workflow import _auth_headers, _bootstrap_reference_data, _create_ticket


@pytest.mark.parametrize("final_action", ["cancel", "no-show", "complete"])
def test_booking_reserves_shared_room_and_final_actions_release(client, final_action):
    institute, employees, services = _bootstrap_reference_data(client)
    manager = _auth_headers("responsable_institut", institute)
    operator = _auth_headers(institute_id=institute)
    prefix = f"/api/v1/resources/institutes/{institute}"
    assert client.patch(f"{prefix}/services/{services[0]['id']}/requirements", headers=manager,
                        json={"skills": [], "resources": [{"kind": "room"}]}).status_code == 200
    assert client.post(prefix, headers=manager, json={"name": "Shared room", "kind": "room"}).status_code == 200
    payload = {"institute_id": institute, "employee_id": employees[0]["id"], "service_id": services[0]["id"],
               "customer_name": "Test", "start_time": (utcnow() + timedelta(minutes=1)).isoformat()}
    booked = client.post("/api/v1/appointments", headers=operator, json=payload)
    assert booked.status_code == 200, booked.text
    appointment_id = booked.json()["id"]
    assert booked.json()["booked_start_time"] == booked.json()["start_time"]
    assert booked.json()["actual_start_time"] is None
    payload["employee_id"] = employees[1]["id"]
    assert client.post("/api/v1/appointments", headers=operator, json=payload).status_code == 400
    ticket = _create_ticket(client, institute, services[0]["id"])
    assign = lambda: client.patch(f"/api/v1/tickets/{ticket['id']}/assign", headers=operator,
                                 json={"employee_id": employees[1]["id"]})
    assert assign().status_code == 400
    if final_action == "complete":
        started = client.patch(f"/api/v1/appointments/{appointment_id}/start", headers=operator)
        assert started.status_code == 200
        assert started.json()["booked_start_time"] == booked.json()["booked_start_time"]
        assert started.json()["booked_end_time"] == booked.json()["booked_end_time"]
        assert started.json()["actual_start_time"] == started.json()["start_time"]
        with Session(main_module.engine) as db:
            assert db.scalar(select(ResourceReservation)).status == "in_use"
    finalized = client.patch(f"/api/v1/appointments/{appointment_id}/{final_action}", headers=operator)
    assert finalized.status_code == 200
    assert (finalized.json()["actual_end_time"] is not None) == (final_action == "complete")
    assert assign().status_code == 200
