from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

import app.main as main_module
from app.modules.institutes.models import Institute
from app.modules.resources.models import Resource, ResourceReservation
from app.modules.resources.reservations import resource_timelines
from app.modules.scheduling.waiting_service import waiting_projections
from test_ticket_workflow import _auth_headers, _bootstrap_reference_data, _create_ticket


def setup(client):
    institute, employees, services = _bootstrap_reference_data(client)
    return institute, employees, services, _auth_headers("responsable_institut", institute), _auth_headers(institute_id=institute)


def test_multiservice_reuses_required_quantity_for_entire_snapshot_duration(client):
    institute, employees, services, manager, operator = setup(client)
    prefix = f"/api/v1/resources/institutes/{institute}"
    for index, quantity in enumerate((2, 1)):
        assert client.patch(f"{prefix}/services/{services[index]['id']}/requirements", headers=manager,
                            json={"skills": [], "resources": [{"kind": "device", "capability": "LASER", "quantity": quantity}]}).status_code == 200
    first = client.post(prefix, headers=manager, json={"name": "Laser one", "kind": "device", "capabilities": ["LASER"]}).json()
    second = client.post(prefix, headers=manager, json={"name": "Other device", "kind": "device"}).json()
    created = client.post("/api/v1/tickets", headers=operator, json={"institute_id": institute,
                         "service_ids": [services[0]["id"], services[1]["id"], services[0]["id"]]})
    assert created.status_code == 200
    ticket = created.json()
    assign = lambda: client.patch(f"/api/v1/tickets/{ticket['id']}/assign", headers=operator,
                                  json={"employee_id": employees[0]["id"]})
    assert assign().status_code == 400
    assert client.patch(f"{prefix}/{second['id']}", headers=manager, json={"capabilities": ["LASER"]}).status_code == 200
    assert assign().status_code == 200
    with Session(main_module.engine) as db:
        rows = db.scalars(select(ResourceReservation).where(ResourceReservation.ticket_id == ticket["id"])).all()
        assert {row.resource_id for row in rows} == {first["id"], second["id"]}
        duration = sum(line["duration_minutes"] * line["quantity"] for line in ticket["lines"])
        assert all(row.end_time - row.start_time == timedelta(minutes=duration) for row in rows)
    assert client.patch(f"/api/v1/tickets/{ticket['id']}/cancel", headers=operator).status_code == 200
    with Session(main_module.engine) as db:
        assert all(row.status == "released" for row in db.scalars(select(ResourceReservation)))


def test_foreign_resource_cannot_satisfy_local_need_or_affect_local_projection(client):
    institute, employees, services, manager, operator = setup(client)
    prefix = f"/api/v1/resources/institutes/{institute}"
    assert client.patch(f"{prefix}/services/{services[0]['id']}/requirements", headers=manager,
                        json={"skills": [], "resources": [{"kind": "room"}]}).status_code == 200
    with Session(main_module.engine) as db:
        origin = db.get(Institute, institute)
        db.add(Institute(id="foreign-test", region_id=origin.region_id, name="Foreign", city="Test"))
        db.flush()
        db.add(Resource(id="foreign-room", institute_id="foreign-test", name="Room", kind="room", capabilities=[], status="active"))
        db.commit()
        assert resource_timelines(db, institute) == []
    ticket = _create_ticket(client, institute, services[0]["id"])
    assert ticket["estimated_start_time"] is None
    assert client.patch(f"/api/v1/tickets/{ticket['id']}/assign", headers=operator,
                        json={"employee_id": employees[0]["id"]}).status_code == 400
    assert client.patch(f"{prefix}/foreign-room", headers=manager, json={"status": "maintenance"}).status_code == 404
    assert client.post(prefix, headers=manager, json={"name": "Local", "kind": "room"}).status_code == 200
    with Session(main_module.engine) as db:
        assert waiting_projections(db, institute)[ticket["id"]].estimated_start_time is not None
