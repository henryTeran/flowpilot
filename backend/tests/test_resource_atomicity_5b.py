import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

import app.main as main_module
from app.modules.resources.models import ResourceReservation
from app.modules.tickets.models import QueueTicket, QueueEvent
from app.modules.tickets.service import assign_ticket
from test_ticket_workflow import _auth_headers, _bootstrap_reference_data, _create_ticket


def test_assignment_commit_failure_rolls_back_resource_ticket_and_event(client, monkeypatch):
    institute, employees, services = _bootstrap_reference_data(client)
    manager = _auth_headers("responsable_institut", institute)
    prefix = f"/api/v1/resources/institutes/{institute}"
    assert client.patch(f"{prefix}/services/{services[0]['id']}/requirements", headers=manager,
                        json={"skills": [], "resources": [{"kind": "room"}]}).status_code == 200
    assert client.post(prefix, headers=manager, json={"name": "Room", "kind": "room"}).status_code == 200
    ticket = _create_ticket(client, institute, services[0]["id"])["id"]
    with Session(main_module.engine) as db:
        event_count = len(db.scalars(select(QueueEvent)).all())
        def fail_commit():
            raise RuntimeError("Injected persistence failure")
        monkeypatch.setattr(db, "commit", fail_commit)
        with pytest.raises(RuntimeError, match="Injected"):
            assign_ticket(db, ticket, employees[0]["id"])
        # This mirrors dependency teardown on a failed HTTP request.
        db.rollback()
    with Session(main_module.engine) as db:
        persisted = db.get(QueueTicket, ticket)
        assert persisted.status == "waiting" and persisted.assigned_employee_id is None
        assert db.scalars(select(ResourceReservation)).all() == []
        assert len(db.scalars(select(QueueEvent)).all()) == event_count
