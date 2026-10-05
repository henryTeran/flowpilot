from sqlalchemy import select
from sqlalchemy.orm import Session

import app.main as main_module
from app.modules.employees.models import Employee
from app.modules.realtime.models import PlanningRevision
from test_ticket_workflow import _auth_headers, _bootstrap_reference_data


def revision(institute):
    with Session(main_module.engine) as db:
        return db.scalar(select(PlanningRevision.revision).where(PlanningRevision.institute_id == institute))


def test_planning_revision_is_commit_visible_and_rolls_back_with_operational_state(client):
    institute, employees, _ = _bootstrap_reference_data(client)
    original = revision(institute)
    with Session(main_module.engine) as db:
        employee = db.get(Employee, employees[0]["id"])
        employee.status = "pause"
        db.flush()
        assert revision(institute) == original
        db.rollback()
    assert revision(institute) == original
    with Session(main_module.engine) as db:
        db.get(Employee, employees[0]["id"]).status = "pause"
        db.commit()
    assert revision(institute) > original
    committed = revision(institute)
    with Session(main_module.engine) as db:
        db.get(Employee, employees[0]["id"]).status = "pause"
        db.commit()
    assert revision(institute) == committed


def test_booking_replay_does_not_emit_another_revision(client):
    from datetime import timedelta
    from app.shared.time import utcnow
    institute, employees, services = _bootstrap_reference_data(client)
    payload = {"institute_id": institute, "employee_id": employees[0]["id"], "service_id": services[0]["id"],
               "customer_name": "Test", "start_time": (utcnow() + timedelta(hours=1)).isoformat(), "idempotency_key": "revision-replay"}
    headers = _auth_headers(institute_id=institute)
    assert client.post("/api/v1/appointments", headers=headers, json=payload).status_code == 200
    committed = revision(institute)
    assert client.post("/api/v1/appointments", headers=headers, json=payload).status_code == 200
    assert revision(institute) == committed
