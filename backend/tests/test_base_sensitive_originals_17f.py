from copy import deepcopy
from datetime import timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from fastapi import HTTPException
from sqlalchemy import select, func, event
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.base import sensitive_originals as operations, sensitive_capabilities as sensitive, read_capabilities as base
from app.modules.base.models import SensitiveOperationOriginal
from app.modules.appointments.models import Appointment, BookingEvent
from app.modules.appointments.schemas import AppointmentCreate, AppointmentUpdate
from app.modules.appointments.service import create_appointment, update_appointment
from app.shared.time import utcnow
from test_ticket_workflow import _auth_headers, _bootstrap_reference_data
from test_postgres_scheduling_4d import postgres_flow


def prepared(engine, institute, employee, service):
    principal = base.Principal(actor_id="signed-manager", institute_id=institute, role="responsable_institut")
    with Session(engine) as db:
        appointment = create_appointment(db, AppointmentCreate(institute_id=institute, employee_id=employee,
            service_id=service, customer_name="Private name", start_time=utcnow()+timedelta(hours=1)))
        preview = sensitive.preview(db, principal, institute, {"appointment_id": appointment.id})
        request = operations.Request(capability="APPOINTMENT_CANCEL", selection={"appointment_id": appointment.id},
            expected_state_fingerprint=preview.state_fingerprint, valid_until=utcnow()+timedelta(minutes=10),
            reason="Explicit cancellation preparation", idempotency_key="operation-one")
    return principal, request


def exercise(engine, principal, request, monkeypatch):
    institute = principal.institute_id
    with Session(engine) as db:
        receipt = operations.create(db, principal, institute, request)
        assert receipt.fingerprint == operations.fingerprint(receipt.original)
        assert receipt.original["effect"] == "prepared_sensitive_operation_only_pending_human_approval_no_execution"
        assert receipt.original["preview"]["state_fingerprint"] == request.expected_state_fingerprint
        assert receipt.original["preview"]["principal"]["actor_id"] == principal.actor_id
        for n in range(24): operations.create(db, principal, institute, request.model_copy(update={"idempotency_key": f"operation-{n}"}))
        assert operations.audit(db, principal, institute).total == 25
        assert len(operations.audit(db, principal, institute).originals) == 20
        assert len(operations.audit(db, principal, institute, 20).originals) == 5
        assert operations.by_key(db, principal, institute, "absent") is None
        assert operations.require(db, principal, institute, receipt.original["id"]) == receipt
        # Expired originals stay recoverable historical records; replay never recaptures.
        monkeypatch.setattr(operations, "utcnow", lambda: request.valid_until+timedelta(minutes=1))
        def no_recapture(*args): raise AssertionError("Recovery must not reload current booking state")
        monkeypatch.setattr(sensitive, "preview", no_recapture)
        assert operations.create(db, principal, institute, request) == receipt
        equivalent = request.model_copy(update={"valid_until": request.valid_until.astimezone(timezone(timedelta(hours=2)))})
        assert operations.create(db, principal, institute, equivalent) == receipt
        assert operations.by_key(db, principal, institute, request.idempotency_key) == receipt
        for candidate, actor in [(request.model_copy(update={"reason": "Changed original terms"}), principal), (request, principal.model_copy(update={"actor_id": "other"}))]:
            with pytest.raises(HTTPException): operations.create(db, actor, institute, candidate)
        row = db.get(SensitiveOperationOriginal, receipt.original["id"])
        raw = deepcopy(receipt.original)
        for attack in (lambda value: value["preview"]["appointment"].update(employee_id="invented"),
                lambda value: value.update(actor_id="other"), lambda value: value.update(valid_until=value["created_at"]),
                lambda value: value["preview"].update(booking_events=999),
                lambda value: value["preview"]["appointment"].update(start_time=request.valid_until.astimezone(timezone(timedelta(hours=2))).isoformat())):
            changed = deepcopy(raw); attack(changed)
            row.original = changed; row.fingerprint = operations.fingerprint(changed); db.commit()
            with pytest.raises(HTTPException): operations.audit(db, principal, institute, 100)
            db.rollback(); row = db.get(SensitiveOperationOriginal, receipt.original["id"])
        row.original = raw; row.fingerprint = receipt.fingerprint; db.commit()
        assert operations.audit(db, principal, institute).total == 25
        assert db.get(Appointment, request.selection.appointment_id).status == "scheduled"
        assert db.scalar(select(func.count()).select_from(BookingEvent)) == 1
    return receipt


def test_sqlite_sensitive_retention_recovery_expiry_and_tamper(client, monkeypatch):
    institute, employees, services = _bootstrap_reference_data(client)
    principal, request = prepared(main_module.engine, institute, employees[0]["id"], services[0]["id"])
    exercise(main_module.engine, principal, request, monkeypatch)


def test_actual_postgres_sensitive_retention_recovery_expiry_and_tamper(postgres_flow, monkeypatch):
    principal, request = prepared(*postgres_flow)
    exercise(postgres_flow[0], principal, request, monkeypatch)


def test_signed_sensitive_preparation_uses_current_version_and_never_approves_or_executes(client):
    institute, employees, services = _bootstrap_reference_data(client)
    principal, request = prepared(main_module.engine, institute, employees[0]["id"], services[0]["id"])
    headers = _auth_headers("responsable_institut", institute)
    prefix = f"/api/v1/base/institutes/{institute}"
    body = request.model_dump(mode="json")
    response = client.post(prefix+"/sensitive-operations", json=body, headers=headers)
    assert response.status_code == 200, response.text
    receipt = response.json()
    assert receipt["original"]["actor_id"] == "test-user"
    assert client.get(prefix+"/sensitive-operation-by-key?key=operation-one", headers=headers).json() == receipt
    assert client.get(prefix+"/sensitive-operations/"+receipt["original"]["id"], headers=headers).json() == receipt
    assert client.get(prefix+"/sensitive-operations", headers=headers).json()["total"] == 1
    for role, owner in [("accueil", institute), ("collaboratrice", institute), ("direction", institute), ("super_admin", institute), ("responsable_institut", "foreign")]:
        denied = _auth_headers(role, owner)
        for suffix in ("/sensitive-operations", "/sensitive-operation-by-key?key=operation-one", "/sensitive-operations/"+receipt["original"]["id"]):
            assert client.get(prefix+suffix, headers=denied).status_code == 403
        assert client.post(prefix+"/sensitive-operations", json=body, headers=denied).status_code == 403
    for field in ("actor_id", "preview", "approved", "execute", "level", "sql", "created_at"):
        assert client.post(prefix+"/sensitive-operations", json={**body, field: "injected"}, headers=headers).status_code == 422
    assert client.post(prefix+"/sensitive-operations", json={**body, "capability": "APPOINTMENT_MOVE"}, headers=headers).status_code == 422
    assert client.post(prefix+"/sensitive-operations", json={**body, "valid_until": "2026-10-08"}, headers=headers).status_code == 422
    with Session(main_module.engine) as db:
        update_appointment(db, request.selection.appointment_id, AppointmentUpdate(notes="Changed private note"), "peer")
    assert client.post(prefix+"/sensitive-operations", json={**body, "idempotency_key": "stale"}, headers=headers).status_code == 400
    # Same-key replay preserves the historical version even after a current change.
    assert client.post(prefix+"/sensitive-operations", json=body, headers=headers).json() == receipt
    fresh = client.post(prefix+"/sensitive-previews/appointment-cancel", json={"appointment_id": request.selection.appointment_id}, headers=headers)
    expired = {**body, "expected_state_fingerprint": fresh.json()["state_fingerprint"], "valid_until": (utcnow()-timedelta(seconds=1)).isoformat(), "idempotency_key": "expired"}
    assert client.post(prefix+"/sensitive-operations", json=expired, headers=headers).status_code == 400
    with Session(main_module.engine) as db:
        assert db.scalar(select(func.count()).select_from(SensitiveOperationOriginal)) == 1
        assert db.get(Appointment, request.selection.appointment_id).status == "scheduled"


@pytest.mark.parametrize("conflicting", [False, True])
def test_actual_postgres_sensitive_same_key_races(postgres_flow, conflicting):
    principal, request = prepared(*postgres_flow)
    engine, institute, *_ = postgres_flow; barrier = Barrier(2)
    def run(n):
        with Session(engine) as db:
            candidate = request.model_copy(update={"reason": "Other explicit reason"}) if n and conflicting else request
            barrier.wait(timeout=10)
            try: return operations.create(db, principal, institute, candidate)
            except HTTPException as error: return error.status_code
    with ThreadPoolExecutor(max_workers=2) as pool: results = list(pool.map(run, range(2)))
    if conflicting: assert sum(isinstance(r, int) and r == 400 for r in results) == 1
    else: assert results[0] == results[1]
    with Session(engine) as db: assert db.scalar(select(func.count()).select_from(SensitiveOperationOriginal)) == 1


def test_actual_postgres_sensitive_rollback_and_committed_lost_ack(postgres_flow, monkeypatch):
    principal, request = prepared(*postgres_flow)
    engine, institute, *_ = postgres_flow
    with Session(engine) as db:
        def fail(*args): raise RuntimeError("forced sensitive flush failure")
        event.listen(db, "after_flush", fail)
        try:
            with pytest.raises(RuntimeError, match="forced sensitive flush"): operations.create(db, principal, institute, request)
        finally: event.remove(db, "after_flush", fail)
        assert db.scalar(select(func.count()).select_from(SensitiveOperationOriginal)) == 0
        commit = db.commit
        def lost_ack(): commit(); raise RuntimeError("committed sensitive acknowledgement lost")
        monkeypatch.setattr(db, "commit", lost_ack)
        with pytest.raises(RuntimeError, match="acknowledgement lost"): operations.create(db, principal, institute, request)
    with Session(engine) as db:
        receipt = operations.by_key(db, principal, institute, request.idempotency_key)
        assert receipt is not None and operations.create(db, principal, institute, request) == receipt
        assert db.scalar(select(func.count()).select_from(SensitiveOperationOriginal)) == 1
