from sqlalchemy import select
from sqlalchemy.orm import Session

import app.main as main_module
from app.modules.resources.models import ResourceReservation
from app.modules.tickets.models import QueueTicket
from test_ticket_workflow import _auth_headers, _bootstrap_reference_data, _create_ticket


def test_shared_resource_assignment_start_extension_finish_and_release(client):
    institute, employees, services = _bootstrap_reference_data(client)
    manager = _auth_headers("responsable_institut", institute)
    operator = _auth_headers(institute_id=institute)
    prefix = f"/api/v1/resources/institutes/{institute}"
    assert client.patch(f"{prefix}/services/{services[0]['id']}/requirements", headers=manager,
                        json={"skills": [], "resources": [{"kind": "room"}]}).status_code == 200
    resource = client.post(prefix, headers=manager, json={"name": "Shared room", "kind": "room"}).json()
    tickets = [_create_ticket(client, institute, services[0]["id"])["id"] for _ in range(2)]
    assign = lambda ticket, employee: client.patch(f"/api/v1/tickets/{ticket}/assign", headers=operator,
                                                   json={"employee_id": employee})
    assert assign(tickets[0], employees[0]["id"]).status_code == 200
    assert client.patch(f"{prefix}/{resource['id']}", headers=manager, json={"status": "maintenance"}).status_code == 400
    assert assign(tickets[1], employees[1]["id"]).status_code == 400
    with Session(main_module.engine) as db:
        assert db.get(QueueTicket, tickets[1]).status == "waiting"
        row = db.scalar(select(ResourceReservation).where(ResourceReservation.ticket_id == tickets[0]))
        reservation_id = row.id
        assert row.status == "reserved" and row.resource_id == resource["id"]
    started = client.post("/api/v1/planning/sessions/start", headers=operator,
                          json={"ticket_id": tickets[0], "employee_id": employees[0]["id"], "service_id": services[0]["id"]})
    assert started.status_code == 200, started.text
    session = started.json()
    extended = client.patch(f"/api/v1/planning/sessions/{session['id']}/extend", headers=operator,
                            json={"minutes": 10, "idempotency_key": "resource-extension"})
    assert extended.status_code == 200, extended.text
    with Session(main_module.engine) as db:
        row = db.get(ResourceReservation, reservation_id)
        assert row.status == "in_use"
        assert row.end_time.isoformat().startswith(extended.json()["planned_end_time"][:19])
        assert len(db.scalars(select(ResourceReservation)).all()) == 1
    assert client.patch(f"/api/v1/planning/sessions/{session['id']}/finish", headers=operator).status_code == 200
    assert assign(tickets[1], employees[1]["id"]).status_code == 200
    assert client.patch(f"/api/v1/tickets/{tickets[1]}/unassign", headers=operator).status_code == 200
    with Session(main_module.engine) as db:
        assert all(row.status == "released" for row in db.scalars(select(ResourceReservation)))
    assert client.post("/api/v1/dev/init-demo-data").status_code == 200
