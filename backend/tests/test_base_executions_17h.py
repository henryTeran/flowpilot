from copy import deepcopy
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from fastapi import HTTPException
from sqlalchemy import select, func, event, text
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.base import executions, approvals, sensitive_capabilities as sensitive
from app.modules.base.models import ExecutionOriginal
from app.modules.appointments.models import Appointment, BookingEvent
from app.modules.appointments.schemas import AppointmentUpdate
from app.modules.appointments.service import update_appointment
from app.modules.resources.models import ResourceReservation
from test_base_approvals_17g import retained, terms
from test_ticket_workflow import _bootstrap_reference_data, _auth_headers
from test_postgres_scheduling_4d import postgres_flow
from test_postgres_resources_5b import shared_room


def authorized(flow):
    principal, operation = retained(flow)
    with Session(flow[0]) as db:
        approval = approvals.decide(db, principal, principal.institute_id, terms(operation))
    request = executions.Request(operation_id=operation.original["id"], operation_fingerprint=operation.fingerprint,
        approval_id=approval.original["id"], approval_fingerprint=approval.fingerprint,
        reason="Explicit approved execution", idempotency_key="execution-one")
    return principal, operation, approval, request


def exercise(flow, monkeypatch):
    engine, institute, *_ = flow
    principal, operation, approval, request = authorized(flow)
    with Session(engine) as db:
        assert executions.for_operation(db, principal, institute, request.operation_id) is None
        receipt = executions.execute(db, principal, institute, request)
        assert receipt.fingerprint == executions.fingerprint(receipt.original)
        assert receipt.original["after"]["status"] == "cancelled"
        assert receipt.original["actor_id"] == principal.actor_id
        assert db.get(Appointment, operation.original["selection"]["appointment_id"]).status == "cancelled"
        assert db.scalar(select(func.count()).select_from(BookingEvent)) == 2
        assert executions.for_operation(db, principal, institute, request.operation_id) == receipt
        monkeypatch.setattr(executions, "utcnow", lambda: executions.Original.model_validate(receipt.original).created_at+timedelta(days=1))
        def no_effect(*args, **kwargs): raise AssertionError("Historical replay must not recapture or execute")
        monkeypatch.setattr(sensitive, "preview", no_effect); monkeypatch.setattr(executions, "cancel_appointment", no_effect)
        assert executions.execute(db, principal, institute, request) == receipt
        assert executions.by_key(db, principal, institute, request.idempotency_key) == receipt
        for body, actor in [(request.model_copy(update={"reason": "Changed request reason"}), principal),
                (request, principal.model_copy(update={"actor_id": "other"})), (request.model_copy(update={"idempotency_key": "new-key"}), principal)]:
            with pytest.raises(HTTPException): executions.execute(db, actor, institute, body)
        with pytest.raises(HTTPException): approvals.decide(db, principal, institute, terms(operation, "revoke", approval, "too-late"))
        row = db.get(ExecutionOriginal, receipt.original["id"])
        bad = deepcopy(receipt.original); bad["after"]["employee_id"] = "invented"
        row.original = bad; row.fingerprint = executions.fingerprint(bad); db.commit()
        with pytest.raises(HTTPException): executions.by_key(db, principal, institute, request.idempotency_key)
        db.rollback(); row = db.get(ExecutionOriginal, receipt.original["id"])
        row.original = deepcopy(receipt.original); row.fingerprint = receipt.fingerprint; db.commit()
        booking_event = db.get(BookingEvent, receipt.original["booking_event_id"])
        booking_event.actor_id = "invented"; db.commit()
        with pytest.raises(HTTPException): executions.by_key(db, principal, institute, request.idempotency_key)


def test_sqlite_execution_receipt_replay_expiry_tamper_and_no_late_revocation(client, monkeypatch):
    institute, employees, services = _bootstrap_reference_data(client)
    exercise((main_module.engine, institute, employees[0]["id"], services[0]["id"]), monkeypatch)


def test_actual_postgres_execution_receipt_replay_expiry_and_tamper(postgres_flow, monkeypatch):
    exercise(postgres_flow, monkeypatch)


@pytest.mark.parametrize("condition", ["pending", "revoked", "changed", "expired", "wrong_reference"])
def test_execution_refusals_never_cancel(client, monkeypatch, condition):
    institute, employees, services = _bootstrap_reference_data(client)
    flow = (main_module.engine, institute, employees[0]["id"], services[0]["id"])
    if condition == "pending":
        principal, operation = retained(flow)
        request = executions.Request(operation_id=operation.original["id"], operation_fingerprint=operation.fingerprint,
            approval_id="missing", approval_fingerprint="0"*64, reason="Explicit request", idempotency_key="pending")
    else: principal, operation, approval, request = authorized(flow)
    with Session(main_module.engine) as db:
        if condition == "revoked": approvals.decide(db, principal, institute, terms(operation, "revoke", approval, "revoke"))
        if condition == "changed": update_appointment(db, operation.original["selection"]["appointment_id"], AppointmentUpdate(notes="Changed private note"), "peer")
        if condition == "expired": monkeypatch.setattr(executions.approvals, "utcnow", lambda: approvals.operations.Original.model_validate(operation.original).valid_until+timedelta(minutes=1))
        if condition == "wrong_reference": request = request.model_copy(update={"approval_fingerprint": "0"*64})
        with pytest.raises(HTTPException): executions.execute(db, principal, institute, request)
        assert db.get(Appointment, operation.original["selection"]["appointment_id"]).status == "scheduled"
        assert db.scalar(select(func.count()).select_from(ExecutionOriginal)) == 0


def test_signed_execution_is_explicit_scoped_and_server_authored(client):
    institute, employees, services = _bootstrap_reference_data(client)
    principal, operation, approval, request = authorized((main_module.engine, institute, employees[0]["id"], services[0]["id"]))
    path = f"/api/v1/base/institutes/{institute}"
    headers = _auth_headers("responsable_institut", institute); body = request.model_dump(mode="json")
    for role, owner in [("accueil", institute), ("collaboratrice", institute), ("direction", institute), ("super_admin", institute), ("responsable_institut", "foreign")]:
        denied = _auth_headers(role, owner)
        assert client.post(path+"/executions", json=body, headers=denied).status_code == 403
        assert client.get(path+"/execution-by-key?key=execution-one", headers=denied).status_code == 403
    for field in ("actor_id", "approved", "before", "after", "created_at", "sql", "commit"):
        assert client.post(path+"/executions", json={**body, field: "injected"}, headers=headers).status_code == 422
    result = client.post(path+"/executions", json=body, headers=headers)
    assert result.status_code == 200, result.text
    assert result.json()["original"]["actor_id"] == "test-user"
    assert client.get(path+"/execution-by-key?key=execution-one", headers=headers).json() == result.json()
    assert client.get(path+"/sensitive-operations/"+request.operation_id+"/execution", headers=headers).json() == result.json()


def test_actual_postgres_business_and_receipt_rollback_and_committed_lost_ack(postgres_flow, monkeypatch):
    shared_room(postgres_flow)
    principal, operation, approval, request = authorized(postgres_flow)
    engine, institute, *_ = postgres_flow
    with Session(engine) as db:
        def fail(session, *_):
            if any(isinstance(row, ExecutionOriginal) for row in session.new): raise RuntimeError("forced receipt flush failure")
        event.listen(db, "after_flush", fail)
        try:
            with pytest.raises(RuntimeError, match="forced receipt"): executions.execute(db, principal, institute, request)
        finally: event.remove(db, "after_flush", fail)
        assert db.get(Appointment, operation.original["selection"]["appointment_id"]).status == "scheduled"
        assert db.scalar(select(ResourceReservation)).status == "reserved"
        assert db.scalar(select(func.count()).select_from(BookingEvent)) == 1
        assert db.scalar(select(func.count()).select_from(ExecutionOriginal)) == 0
        commit = db.commit
        def lost_ack(): commit(); raise RuntimeError("committed execution acknowledgement lost")
        monkeypatch.setattr(db, "commit", lost_ack)
        with pytest.raises(RuntimeError, match="acknowledgement lost"): executions.execute(db, principal, institute, request)
    with Session(engine) as db:
        receipt = executions.by_key(db, principal, institute, request.idempotency_key)
        assert receipt is not None and executions.execute(db, principal, institute, request) == receipt
        assert db.scalar(select(ResourceReservation)).status == "released"
        assert db.scalar(select(func.count()).select_from(BookingEvent)) == 2
        assert db.scalar(select(func.count()).select_from(ExecutionOriginal)) == 1


@pytest.mark.parametrize("same_key", [False, True])
def test_actual_postgres_competing_execution_requests_have_one_effect(postgres_flow, same_key):
    principal, operation, approval, request = authorized(postgres_flow)
    engine, institute, *_ = postgres_flow; barrier = Barrier(2)
    def run(n):
        with Session(engine) as db:
            body = request if same_key or n == 0 else request.model_copy(update={"idempotency_key": "other"})
            barrier.wait(timeout=10)
            try: return executions.execute(db, principal, institute, body)
            except HTTPException as error: return error.status_code
    with ThreadPoolExecutor(max_workers=2) as pool: results = list(pool.map(run, range(2)))
    if same_key: assert results[0] == results[1]
    else: assert sum(isinstance(r, int) and r == 400 for r in results) == 1
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(ExecutionOriginal)) == 1
        assert db.scalar(select(func.count()).select_from(BookingEvent)) == 2


def test_actual_postgres_non_utc_connection_preserves_reviewed_version_and_event_proof(postgres_flow):
    principal, operation, approval, request = authorized(postgres_flow)
    engine, institute, *_ = postgres_flow
    with Session(engine) as db:
        db.execute(text("SET TIME ZONE 'Europe/Paris'"))
        preview = sensitive.preview(db, principal, institute, {"appointment_id": operation.original["selection"]["appointment_id"]})
        assert preview.state_fingerprint == operation.original["expected_state_fingerprint"]
        receipt = executions.execute(db, principal, institute, request)
        assert receipt.original["after"]["start_time"].endswith("Z")
    with Session(engine) as db:
        assert executions.by_key(db, principal, institute, request.idempotency_key) == receipt


def test_actual_postgres_execution_and_revocation_race_has_one_winner(postgres_flow):
    principal, operation, approval, request = authorized(postgres_flow)
    engine, institute, *_ = postgres_flow; barrier = Barrier(2)
    def run(n):
        with Session(engine) as db:
            barrier.wait(timeout=10)
            try:
                if n == 0: return executions.execute(db, principal, institute, request)
                return approvals.decide(db, principal, institute, terms(operation, "revoke", approval, "revoke"))
            except HTTPException as error: return error.status_code
    with ThreadPoolExecutor(max_workers=2) as pool: results = list(pool.map(run, range(2)))
    assert sum(isinstance(r, int) and r == 400 for r in results) == 1
    with Session(engine) as db:
        status = approvals.state(db, principal, institute, request.operation_id).status
        executions_count = db.scalar(select(func.count()).select_from(ExecutionOriginal))
        assert (status, executions_count) in {("approved", 1), ("revoked", 0)}
        assert db.get(Appointment, operation.original["selection"]["appointment_id"]).status == ("cancelled" if executions_count else "scheduled")
