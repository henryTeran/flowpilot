from sqlalchemy import select
from sqlalchemy.orm import Session

import app.main as main_module
from app.modules.employees.models import Employee
from app.modules.institutes.models import Institute
from app.modules.realtime.revisions import mark_planning_changed
from app.modules.realtime.models import PlanningRevision
from test_realtime_tenant_isolation_2b import _ws_token
from test_ticket_workflow import _bootstrap_reference_data, _create_ticket


def test_websocket_notifies_after_a_committed_queue_write(client):
    institute, _, services = _bootstrap_reference_data(client)
    token = _ws_token(institute_id=institute)
    with client.websocket_connect(f"/ws/institutes/{institute}/planning?token={token}") as ws:
        _create_ticket(client, institute, services[0]["id"])
        message = ws.receive_json()
        assert message["event"] == "planning.changed"
        assert message["revision"] > 0
        assert set(message) == {"event", "revision"}


def test_rollback_and_foreign_commit_do_not_change_connected_tenant(client):
    institute, employees, _ = _bootstrap_reference_data(client)
    token = _ws_token(institute_id=institute)
    with Session(main_module.engine) as db:
        origin = db.get(Institute, institute)
        db.add(Institute(id="foreign-realtime", region_id=origin.region_id, name="Foreign", city="Test"))
        db.commit()
    with client.websocket_connect(f"/ws/institutes/{institute}/planning?token={token}") as ws:
        with Session(main_module.engine) as db:
            original = db.scalar(select(PlanningRevision.revision).where(PlanningRevision.institute_id == institute))
            db.get(Employee, employees[0]["id"]).status = "pause"
            db.flush()
            db.rollback()
            mark_planning_changed(db, "foreign-realtime")
            db.commit()
            assert db.scalar(select(PlanningRevision.revision).where(PlanningRevision.institute_id == institute)) == original
        # A committed update to this tenant must be the first change observed;
        # foreign/rolled-back changes must not produce an earlier notification.
        with Session(main_module.engine) as db:
            db.get(Employee, employees[0]["id"]).status = "pause"
            db.commit()
            expected = db.scalar(select(PlanningRevision.revision).where(PlanningRevision.institute_id == institute))
        message = ws.receive_json()
        assert message["event"] == "planning.changed"
        assert message["revision"] == expected
