from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import app.main as main_module
from app.modules.workforce import absences
from app.modules.workforce.absence_schemas import AbsenceCreate, AbsenceCancel
from app.modules.workforce.models import EmployeeAbsence, AbsenceCancellation
from app.modules.appointments.schemas import AppointmentCreate
from app.modules.appointments.service import create_appointment
from app.modules.employees.models import Employee
from app.modules.scheduling.waiting_service import waiting_projections
from app.shared.time import utcnow
from test_ticket_workflow import _auth_headers, _bootstrap_reference_data, _create_ticket
from test_postgres_scheduling_4d import postgres_flow


def setup(client):
    institute, employees, services = _bootstrap_reference_data(client)
    return institute, employees[0]["id"], services[0]["id"], f"/api/v1/workforce/institutes/{institute}", _auth_headers("responsable_institut", institute)


def payload(employee, start=None, key="original"):
    start = start or utcnow() + timedelta(days=1)
    return {"employee_id": employee, "kind": "leave", "start_time": start.isoformat(),
            "end_time": (start + timedelta(hours=1)).isoformat(), "reason": "Absence planifiee", "idempotency_key": key}


def test_original_absence_and_cancellation_keep_terms_actor_replay_and_recovery(client):
    institute, employee, _, path, headers = setup(client)
    body = payload(employee)
    created = client.post(path + "/absences", headers=headers, json=body)
    assert created.status_code == 200, created.text
    original = created.json()
    assert original["actor_id"] == "test-user" and original["start_time"].endswith("Z")
    assert client.post(path + "/absences", headers=headers, json=body).json() == original
    assert client.get(path + "/absences/original/original", headers=headers).json() == original
    assert client.get(path + "/absences/original/missing", headers=headers).json() is None
    assert client.post(path + "/absences", headers=headers, json={**body, "reason": "Changed"}).status_code == 400
    changed = {**body, "idempotency_key": "overlap"}
    assert client.post(path + "/absences", headers=headers, json=changed).status_code == 400
    cancel = {"reason": "Reprise du creneau", "idempotency_key": "cancel-original"}
    cancellation = client.post(f"{path}/absences/{original['id']}/cancel", headers=headers, json=cancel)
    assert cancellation.status_code == 200, cancellation.text
    assert client.post(f"{path}/absences/{original['id']}/cancel", headers=headers, json=cancel).json() == cancellation.json()
    assert client.get(path + "/absence-cancellations/original/cancel-original", headers=headers).json() == cancellation.json()
    assert client.post(f"{path}/absences/{original['id']}/cancel", headers=headers, json={**cancel, "idempotency_key": "another"}).status_code == 400
    recovered = client.get(path + "/absences/original/original", headers=headers).json()
    assert recovered["cancellation"] == cancellation.json()
    assert recovered["start_time"] == original["start_time"] and recovered["reason"] == original["reason"]
    assert client.post(path + "/absences", headers=headers, json=changed).status_code == 200
    with Session(main_module.engine) as db:
        assert len(list(db.scalars(select(EmployeeAbsence)))) == 2
        assert len(list(db.scalars(select(AbsenceCancellation)))) == 1


def test_absence_roles_foreign_ownership_dates_and_half_open_edges(client):
    institute, employee, _, path, headers = setup(client)
    body = payload(employee)
    for role, tenant in [("accueil", institute), ("collaboratrice", institute), ("responsable_institut", None), ("responsable_institut", "foreign")]:
        auth = _auth_headers(role, tenant)
        assert client.post(path + "/absences", headers=auth, json=body).status_code == 403
        assert client.get(path + "/absences", headers=auth).status_code == 403
    assert client.get(path + "/absences").status_code == 403
    for changes in [{"start_time": "2026-10-08T12:00:00"}, {"end_time": body["start_time"]}, {"kind": "illness"}, {"actor_id": "spoof"}]:
        assert client.post(path + "/absences", headers=headers, json={**body, **changes}).status_code == 422
    assert client.post(path + "/absences", headers=headers, json={**body, "employee_id": "foreign"}).status_code == 404
    assert client.get(path + "/absences?employee_id=foreign", headers=headers).status_code == 404
    assert client.get(path + "/absences?limit=101", headers=headers).status_code == 422
    assert client.post(path + "/absences", headers=headers, json=body).status_code == 200
    edge = {**body, "start_time": body["end_time"], "end_time": (utcnow() + timedelta(days=1, hours=2)).isoformat(), "idempotency_key": "edge"}
    assert client.post(path + "/absences", headers=headers, json=edge).status_code == 200
    assert len(client.get(path + "/absences?limit=1", headers=headers).json()) == 1
    assert len(client.get(path + "/absences?limit=1&offset=1", headers=headers).json()) == 1


def test_active_absence_blocks_assignment_start_and_projects_known_return_without_mutating_status(client):
    institute, employee, service, path, headers = setup(client)
    now = utcnow()
    body = payload(employee, now - timedelta(seconds=1))
    original = client.post(path + "/absences", headers=headers, json=body)
    assert original.status_code == 200, original.text
    operator = _auth_headers(institute_id=institute)
    ticket = _create_ticket(client, institute, service)
    assert client.patch(f"/api/v1/tickets/{ticket['id']}/assign", headers=operator, json={"employee_id": employee}).status_code == 400
    assert client.post("/api/v1/planning/sessions/start", headers=operator, json={"ticket_id": ticket["id"], "employee_id": employee, "service_id": service}).status_code == 400
    current = client.get(f"/api/v1/availability/employees/{employee}?institute_id={institute}", headers=operator).json()
    assert current["available"] is False and current["current_slot"]["reason"] == "scheduled_absence"
    assert current["current_slot"]["blocking_absence_id"] == original.json()["id"]
    assert current["current_slot"]["blocking_appointment_id"] is None
    planning = client.get(f"/api/v1/planning/institutes/{institute}/availability", headers=operator).json()
    assert next(row for row in planning["employees"] if row["employee_id"] == employee)["employee_status"] == "absent"
    with Session(main_module.engine) as db:
        assert db.get(Employee, employee).status == "available"
        for other in db.scalars(select(Employee).where(Employee.institute_id == institute, Employee.id != employee)):
            other.status = "offline"
        db.commit()
        projected = waiting_projections(db, institute, now=now, new_duration=10)
        assert projected["__new_arrival__"].estimated_start_time >= AbsenceCreate.model_validate(body).end_time
    cancelled = client.post(f"{path}/absences/{original.json()['id']}/cancel", headers=headers, json={"reason": "Retour", "idempotency_key": "release"})
    assert cancelled.status_code == 200
    assert client.patch(f"/api/v1/tickets/{ticket['id']}/assign", headers=operator, json={"employee_id": employee}).status_code == 200


def test_absence_booking_create_move_and_committed_slot_protection(client):
    institute, employee, service, path, headers = setup(client)
    body = payload(employee)
    original = client.post(path + "/absences", headers=headers, json=body)
    assert original.status_code == 200
    booking = {"institute_id": institute, "employee_id": employee, "service_id": service, "customer_name": "Test", "start_time": body["start_time"]}
    assert client.post("/api/v1/appointments", headers=headers, json=booking).status_code == 400
    after = {**booking, "start_time": body["end_time"]}
    accepted = client.post("/api/v1/appointments", headers=headers, json=after)
    assert accepted.status_code == 200, accepted.text
    assert client.patch(f"/api/v1/appointments/{accepted.json()['id']}", headers=headers, json={"start_time": body["start_time"]}).status_code == 400
    conflict = {**body, "start_time": after["start_time"], "end_time": (AbsenceCreate.model_validate(body).end_time + timedelta(hours=1)).isoformat(), "idempotency_key": "booked"}
    assert client.post(path + "/absences", headers=headers, json=conflict).status_code == 400


def test_future_absence_rejects_session_extension_and_preserves_original_end(client, monkeypatch):
    institute, employee, service, path, headers = setup(client)
    ticket = _create_ticket(client, institute, service)
    started = client.post("/api/v1/planning/sessions/start", headers=headers,
        json={"ticket_id": ticket["id"], "employee_id": employee, "service_id": service})
    assert started.status_code == 200, started.text
    from app.shared.time import explicit_utc_instant
    end = datetime.fromisoformat(started.json()["planned_end_time"])
    # A real execution may end before the absence; extending it crosses the boundary.
    original = client.post(path + "/absences", headers=headers,
        json=payload(employee, end + timedelta(minutes=1)))
    assert original.status_code == 200, original.text
    identifier = started.json()["id"]
    rejected = client.patch(f"/api/v1/planning/sessions/{identifier}/extend", headers=headers,
        json={"minutes": 5, "idempotency_key": "cross-absence"})
    assert rejected.status_code == 400, rejected.text
    from app.modules.planning.models import ServiceSession
    with Session(main_module.engine) as db:
        assert explicit_utc_instant(db.get(ServiceSession, identifier).planned_end_time) == end
        import app.modules.planning.service as planning
        with monkeypatch.context() as clock:
            clock.setattr(planning, "utcnow", lambda: end + timedelta(minutes=2))
            day = planning.get_day_planning(db, institute)
            assert next(row for row in day.rows if row.employee_id == employee).employee_status == "delayed"
    assert client.post(f"{path}/absences/{original.json()['id']}/cancel", headers=headers,
        json={"reason": "Return", "idempotency_key": "release-extension"}).status_code == 200
    accepted = client.patch(f"/api/v1/planning/sessions/{identifier}/extend", headers=headers,
        json={"minutes": 5, "idempotency_key": "cross-absence"})
    assert accepted.status_code == 200, accepted.text


def test_actual_postgres_absence_and_booking_cannot_commit_overlapping_claims(postgres_flow):
    engine, institute, employee, service = postgres_flow
    start = utcnow() + timedelta(days=1)
    absence = AbsenceCreate.model_validate(payload(employee, start))
    booking = AppointmentCreate(institute_id=institute, employee_id=employee, service_id=service, customer_name="Test", start_time=start)
    barrier = Barrier(2)
    def perform(action):
        with Session(engine) as db:
            barrier.wait(timeout=10)
            try:
                action(db); return "ok"
            except HTTPException as error:
                db.rollback(); assert error.status_code == 400; return "conflict"
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(perform, lambda db: absences.create(db, institute, absence, "signed-manager")),
                   pool.submit(perform, lambda db: create_appointment(db, booking, "signed-manager"))]
        assert sorted(future.result(timeout=20) for future in futures) == ["conflict", "ok"]


def test_actual_postgres_same_key_race_recovers_one_original_and_rejects_changed_actor(postgres_flow):
    engine, institute, employee, _ = postgres_flow
    body = AbsenceCreate.model_validate(payload(employee))
    barrier = Barrier(2)
    def create():
        with Session(engine) as db:
            barrier.wait(timeout=10)
            return absences.create(db, institute, body, "signed-manager").id
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(create) for _ in range(2)]
        identifiers = [future.result(timeout=20) for future in futures]
    assert identifiers[0] == identifiers[1]
    with Session(engine) as db:
        assert len(list(db.scalars(select(EmployeeAbsence)))) == 1
        with pytest.raises(HTTPException) as error:
            absences.create(db, institute, body, "different-manager")
        assert error.value.status_code == 400
        db.rollback()
        cancellation = AbsenceCancel(reason="Return", idempotency_key="return")
        absences.cancel(db, institute, identifiers[0], cancellation, "signed-manager")
        recovered = absences.create(db, institute, body, "signed-manager")
        assert recovered.id == identifiers[0] and recovered.cancellation is not None


def test_actual_postgres_database_rejects_foreign_employee_and_cancellation_owner(postgres_flow):
    engine, institute, employee, _ = postgres_flow
    now = utcnow()
    with Session(engine) as db:
        original = absences.create(db, institute, AbsenceCreate.model_validate(payload(employee)), "signed")
        db.add(EmployeeAbsence(id="foreign-absence", institute_id="foreign-owner", employee_id=employee,
            kind="leave", start_time=now, end_time=now + timedelta(hours=1), reason="Fixture",
            actor_id="signed", idempotency_key="foreign", created_at=now))
        with pytest.raises(IntegrityError) as error:
            db.commit()
        assert error.value.orig.diag.constraint_name == "fk_absence_employee_owner"
        db.rollback()
        db.add(AbsenceCancellation(id="foreign-cancel", institute_id="foreign-owner", absence_id=original.id,
            reason="Fixture", actor_id="signed", idempotency_key="foreign", created_at=now))
        with pytest.raises(IntegrityError) as error:
            db.commit()
        assert error.value.orig.diag.constraint_name == "fk_absence_cancel_owner"
        db.rollback()
        assert absences.snapshot(db, db.get(EmployeeAbsence, original.id)).cancellation is None
