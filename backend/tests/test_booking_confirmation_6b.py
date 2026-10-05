from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

import app.main as main_module
from app.modules.resources.models import ResourceReservation
from app.modules.appointments.models import BookingEvent
from app.shared.time import utcnow
from test_ticket_workflow import _auth_headers, _bootstrap_reference_data


def test_confirmation_replay_preserves_booked_interval_and_resource(client):
    institute, employees, services = _bootstrap_reference_data(client)
    manager = _auth_headers("responsable_institut", institute)
    operator = _auth_headers(institute_id=institute)
    prefix = f"/api/v1/resources/institutes/{institute}"
    assert client.patch(f"{prefix}/services/{services[0]['id']}/requirements", headers=manager,
                        json={"skills": [], "resources": [{"kind": "room"}]}).status_code == 200
    assert client.post(prefix, headers=manager, json={"name": "Room", "kind": "room"}).status_code == 200
    created = client.post("/api/v1/appointments", headers=operator,
                          json={"institute_id": institute, "service_id": services[0]["id"],
                                "employee_id": employees[0]["id"], "customer_name": "Test",
                                "start_time": (utcnow() + timedelta(hours=1)).isoformat()})
    assert created.status_code == 200
    appointment = created.json()
    path = f"/api/v1/appointments/{appointment['id']}/confirm"
    assert client.patch(path, headers=_auth_headers(institute_id="foreign")).status_code == 403
    first = client.patch(path, headers=operator)
    replay = client.patch(path, headers=operator)
    assert first.status_code == replay.status_code == 200
    assert first.json() == replay.json()
    assert first.json()["status"] == "confirmed"
    assert first.json()["booked_start_time"] == appointment["booked_start_time"]
    with Session(main_module.engine) as db:
        rows = db.scalars(select(ResourceReservation)).all()
        assert len(rows) == 1 and rows[0].status == "reserved"
        events = db.scalars(select(BookingEvent).order_by(BookingEvent.occurred_at)).all()
        assert [event.event_type for event in events] == ["created", "confirmed"]
        assert all(event.actor_id == "test-user" for event in events)
        assert events[1].before["status"] == "scheduled" and events[1].after["status"] == "confirmed"
        assert all("customer_name" not in event.after and "phone" not in event.after for event in events)
    assert client.patch(f"/api/v1/appointments/{appointment['id']}/cancel", headers=operator).status_code == 200
    assert client.patch(path, headers=operator).status_code == 400
    assert client.patch("/api/v1/appointments/missing/confirm", headers=operator).status_code == 404
