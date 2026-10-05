from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

import app.main as main_module
from app.modules.appointments.models import Appointment
from app.modules.resources.models import ResourceReservation
from app.shared.time import utcnow
from test_ticket_workflow import _auth_headers, _bootstrap_reference_data, _create_ticket


def test_move_revalidates_resource_and_employee_without_losing_old_booking(client):
    institute, employees, services = _bootstrap_reference_data(client)
    operator = _auth_headers(institute_id=institute)
    manager = _auth_headers("responsable_institut", institute)
    prefix = f"/api/v1/resources/institutes/{institute}"
    assert client.patch(f"{prefix}/services/{services[0]['id']}/requirements", headers=manager,
                        json={"skills": [], "resources": [{"kind": "room"}]}).status_code == 200
    assert client.post(prefix, headers=manager, json={"name": "Room", "kind": "room"}).status_code == 200
    now = utcnow()
    def book(employee, hour):
        response = client.post("/api/v1/appointments", headers=operator, json={"institute_id": institute,
            "employee_id": employee, "service_id": services[0]["id"], "customer_name": "Test",
            "start_time": (now + timedelta(hours=hour)).isoformat()})
        assert response.status_code == 200, response.text
        return response.json()
    first = book(employees[0]["id"], 1)
    second = book(employees[1]["id"], 2)
    path = f"/api/v1/appointments/{first['id']}"
    assert client.patch(path, headers=operator, json={"start_time": second["start_time"]}).status_code == 400
    with Session(main_module.engine) as db:
        appointment = db.get(Appointment, first["id"])
        row = db.scalar(select(ResourceReservation).where(ResourceReservation.appointment_id == first["id"]))
        assert appointment.start_time == row.start_time
        assert appointment.start_time.isoformat().startswith(first["start_time"][:19])
    changed = client.patch(path, headers=operator, json={"start_time": (now + timedelta(hours=3)).isoformat(),
                                                      "employee_id": employees[1]["id"], "notes": "Moved"})
    assert changed.status_code == 200, changed.text
    assert changed.json()["booked_start_time"] == changed.json()["start_time"]
    assert changed.json()["actual_start_time"] is None
    replay = client.patch(path, headers=operator, json={"start_time": changed.json()["start_time"]})
    assert replay.json() == changed.json()
    assert client.patch(path, headers=_auth_headers(institute_id="foreign"), json={"notes": "No"}).status_code == 403
    assert client.patch(path, headers=_auth_headers(institute_id=None), json={"notes": "No"}).status_code == 403
    assert client.patch(path, headers=operator, json={"start_time": None}).status_code == 400
    assert client.patch(path, headers=operator, json={"start_time": (now - timedelta(hours=1)).isoformat()}).status_code == 400
    assert client.patch(path, headers=operator, json={"status": "completed"}).status_code == 422
    assert client.patch(path + "/cancel", headers=operator).status_code == 200
    assert client.patch(path, headers=operator, json={"notes": "Too late"}).status_code == 400


def test_move_cannot_displace_assigned_walkin(client):
    institute, employees, services = _bootstrap_reference_data(client)
    operator = _auth_headers(institute_id=institute)
    created = client.post("/api/v1/appointments", headers=operator, json={"institute_id": institute,
        "employee_id": employees[0]["id"], "service_id": services[0]["id"], "customer_name": "Test",
        "start_time": (utcnow() + timedelta(hours=2)).isoformat()})
    assert created.status_code == 200
    ticket = _create_ticket(client, institute, services[0]["id"])
    assert client.patch(f"/api/v1/tickets/{ticket['id']}/assign", headers=operator,
                        json={"employee_id": employees[0]["id"]}).status_code == 200
    assert client.patch(f"/api/v1/appointments/{created.json()['id']}", headers=operator,
                        json={"start_time": (utcnow() + timedelta(minutes=1)).isoformat()}).status_code == 400
