from datetime import timedelta
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
import app.main as main_module
from app.database.session import get_db
from app.modules.base import move_capability as move, move_execution, sensitive_originals as operations, approvals, executions
from app.modules.base.read_capabilities import Principal
from app.modules.base.models import ExecutionOriginal
from app.modules.appointments.models import Appointment, BookingEvent
from app.modules.appointments.schemas import AppointmentCreate, AppointmentUpdate
from app.modules.appointments.service import create_appointment, update_appointment, cancel_appointment
from app.modules.resources.models import Resource, ResourceRequirement, ResourceReservation
from app.modules.services.models import Service
from app.modules.waitlist.originals import fingerprint
from app.shared.time import utcnow, explicit_utc_instant
from test_ticket_workflow import _bootstrap_reference_data, _auth_headers
from test_postgres_scheduling_4d import postgres_flow, race


def authorized(flow, *, change_service=False, approve=True):
    engine, institute, employee, service = flow
    principal = Principal(actor_id="test-user", institute_id=institute, role="responsable_institut")
    with Session(engine) as db:
        source_service = db.get(Service, service)
        source_service.requires_machine = False
        db.add(Resource(id="move-exec-room", institute_id=institute, name="Move exec room", kind="room", capabilities=[], status="active"))
        db.add(ResourceRequirement(id="move-exec-need", institute_id=institute, service_id=service, kind="room", capability="", quantity=1))
        if change_service:
            db.add(Service(id="move-target-service", category_id=source_service.category_id, name="Explicit target service",
                duration_min=25, duration_max=25, requires_machine=False, status="active"))
            db.add(Resource(id="move-target-device", institute_id=institute, name="Target device", kind="device", capabilities=[], status="active"))
            db.flush()
            db.add(ResourceRequirement(id="move-target-need", institute_id=institute, service_id="move-target-service", kind="device", capability="", quantity=1))
        db.commit()
        booked = create_appointment(db, AppointmentCreate(institute_id=institute, employee_id=employee, service_id=service,
            customer_name="Unchanged customer", phone="+33123456789", notes="Unchanged private note", start_time=utcnow()+timedelta(hours=2)))
        selection = dict(appointment_id=booked.id, start_time=(explicit_utc_instant(booked.start_time)+timedelta(minutes=1)).isoformat())
        if change_service:
            selection["service_id"] = "move-target-service"
        preview = move.preview(db, principal, institute, selection)
        operation = operations.create(db, principal, institute, operations.Request(capability="APPOINTMENT_MOVE", selection=selection,
            expected_state_fingerprint=preview.state_fingerprint, valid_until=utcnow()+timedelta(minutes=15), reason="Reviewed exact move", idempotency_key="move-operation"))
        approval = approvals.decide(db, principal, institute, approvals.Request(operation_id=operation.original["id"], operation_fingerprint=operation.fingerprint,
            previous_id=None, previous_fingerprint=None, decision="approve", reason="Explicit approved move", idempotency_key="move-approval")) if approve else None
    request = executions.Request(operation_id=operation.original["id"], operation_fingerprint=operation.fingerprint,
        approval_id=approval.original["id"] if approval else "missing", approval_fingerprint=approval.fingerprint if approval else "0"*64,
        reason="Execute exact approved move", idempotency_key="move-execution")
    return principal, operation, request


def assert_effect(flow, operation, performed):
    engine, institute, *_ = flow
    source = operations.Original.model_validate(operation.original).preview
    with Session(engine) as db:
        booking = db.get(Appointment, source.selection.appointment_id)
        assert explicit_utc_instant(booking.start_time) == (source.proposed if performed else source.appointment).start_time
        assert len(db.scalars(select(Appointment)).all()) == 1
        assert len(db.scalars(select(BookingEvent)).all()) == (2 if performed else 1)
        assert len(db.scalars(select(ExecutionOriginal)).all()) == (1 if performed else 0)


def exercise(client, flow, monkeypatch):
    engine, institute, *_ = flow
    principal, operation, request = authorized(flow, change_service=True)
    headers = _auth_headers("responsable_institut", institute)
    body = request.model_dump(mode="json")
    assert client.post("/api/v1/copilot/execute", headers=_auth_headers("accueil", institute), json=body).status_code == 403
    assert client.post("/api/v1/copilot/execute", headers=headers, json={**body, "approved": True}).status_code == 422
    with Session(engine) as db:
        db.get(Resource, "move-target-device").status = "maintenance"
        db.commit()
    assert client.post("/api/v1/copilot/execute", headers=headers, json=body).status_code == 400
    assert_effect(flow, operation, False)
    with Session(engine) as db:
        db.get(Resource, "move-target-device").status = "active"
        db.commit()
    assert client.post("/api/v1/copilot/execute", headers=headers, json={**body, "approval_fingerprint": "0"*64}).status_code == 400
    response = client.post("/api/v1/copilot/execute", headers=headers, json=body)
    assert response.status_code == 200, response.text
    receipt = response.json()
    assert receipt["fingerprint"] == fingerprint(receipt["original"])
    original = move_execution.Original.model_validate(receipt["original"])
    assert original.after.service_id == "move-target-service"
    assert original.after.end_time-original.after.start_time == timedelta(minutes=25)
    assert original.before_metadata_digest == original.after_metadata_digest
    assert "Unchanged private" not in response.text and "+33123456789" not in response.text
    assert_effect(flow, operation, True)
    with Session(engine) as db:
        booking = db.get(Appointment, original.appointment_id)
        assert booking.customer_name == "Unchanged customer" and booking.notes == "Unchanged private note" and booking.phone == "+33123456789"
        rows = list(db.scalars(select(ResourceReservation).where(ResourceReservation.appointment_id == booking.id)))
        assert {row.resource_id: row.status for row in rows} == {"move-exec-room": "released", "move-target-device": "reserved"}
        target = next(row for row in rows if row.status == "reserved")
        assert explicit_utc_instant(target.start_time) == original.after.start_time and explicit_utc_instant(target.end_time) == original.after.end_time
        # Source/event binding remains required even if both storage hashes are rewritten.
        event = db.get(BookingEvent, original.booking_event_id)
        saved_before = dict(event.before)
        event.before = {**saved_before, "employee_id": "substituted"}
        execution = db.scalar(select(ExecutionOriginal).where(ExecutionOriginal.operation_id == request.operation_id))
        altered = {**receipt["original"], "booking_event_fingerprint": fingerprint(executions.event_raw(event))}
        execution.original, execution.fingerprint = altered, fingerprint(altered)
        db.commit()
        with pytest.raises(HTTPException):
            executions.by_key(db, principal, institute, request.idempotency_key)
        db.rollback()
        event.before = saved_before
        execution.original, execution.fingerprint = receipt["original"], receipt["fingerprint"]
        db.commit()
        cancel_appointment(db, booking.id, "later-actor")
    monkeypatch.setattr(executions, "utcnow", lambda: original.created_at+timedelta(days=1))
    def no_effect(*args, **kwargs):
        raise AssertionError("Historical replay must not revalidate or move")
    monkeypatch.setattr(move, "preview", no_effect)
    monkeypatch.setattr(move_execution, "update_appointment", no_effect)
    assert client.post("/api/v1/copilot/execute", headers=headers, json=body).json() == receipt
    assert client.post("/api/v1/copilot/execute", headers=headers, json={**body, "idempotency_key": "new-key"}).status_code == 400
    with Session(engine) as db:
        assert executions.by_key(db, principal, institute, request.idempotency_key).original == receipt["original"]
        old = {**operation.original, "preview": {**operation.original["preview"], "capability": {
            **operation.original["preview"]["capability"], "execution_registered": False}}}
        assert operations.Original.model_validate(old).preview.capability.execution_registered is False
    discovery = client.get("/api/v1/copilot/execution-capabilities", headers=headers)
    assert {row["name"] for row in discovery.json()} == {"APPOINTMENT_CREATE", "APPOINTMENT_MOVE"}


def test_sqlite_signed_atomic_move_and_historical_replay(client, monkeypatch):
    institute, employees, services = _bootstrap_reference_data(client)
    exercise(client, (main_module.engine, institute, employees[0]["id"], services[0]["id"]), monkeypatch)


def test_postgres_signed_atomic_move_and_historical_replay(client, postgres_flow, monkeypatch):
    engine, *_ = postgres_flow
    def database():
        with Session(engine) as db:
            yield db
    main_module.app.dependency_overrides[get_db] = database
    monkeypatch.setattr(main_module, "engine", engine)
    exercise(client, postgres_flow, monkeypatch)


def test_postgres_move_rollback_and_lost_ack(postgres_flow, monkeypatch):
    engine, institute, *_ = postgres_flow
    principal, operation, request = authorized(postgres_flow)
    verify = executions.verify
    def fail(*args):
        raise RuntimeError("Injected failure after move writes")
    monkeypatch.setattr(executions, "verify", fail)
    with Session(engine) as db:
        with pytest.raises(RuntimeError):
            executions.execute(db, principal, institute, request)
    assert_effect(postgres_flow, operation, False)
    monkeypatch.setattr(executions, "verify", verify)
    with Session(engine) as db:
        commit = db.commit
        def lost_ack():
            commit()
            raise RuntimeError("Injected acknowledgement loss")
        monkeypatch.setattr(db, "commit", lost_ack)
        with pytest.raises(RuntimeError):
            executions.execute(db, principal, institute, request)
    assert_effect(postgres_flow, operation, True)
    with Session(engine) as db:
        assert executions.execute(db, principal, institute, request) == executions.for_operation(db, principal, institute, request.operation_id)


@pytest.mark.parametrize("same_key", [True, False])
def test_postgres_competing_moves_have_one_effect(postgres_flow, same_key):
    engine, institute, *_ = postgres_flow
    principal, operation, request = authorized(postgres_flow)
    other = request if same_key else request.model_copy(update={"idempotency_key": "competing-key"})
    results = race(engine, [lambda db: executions.execute(db, principal, institute, request).original and db.scalar(select(Appointment)),
        lambda db: executions.execute(db, principal, institute, other).original and db.scalar(select(Appointment))])
    assert sorted(status for status, _ in results) == (["ok", "ok"] if same_key else ["conflict", "ok"])
    assert_effect(postgres_flow, operation, True)


@pytest.mark.parametrize("condition", ["pending", "revoked", "expired", "source_changed"])
def test_move_without_current_valid_approval_never_moves(client, monkeypatch, condition):
    institute, employees, services = _bootstrap_reference_data(client)
    flow = main_module.engine, institute, employees[0]["id"], services[0]["id"]
    principal, operation, request = authorized(flow, approve=condition != "pending")
    with Session(main_module.engine) as db:
        if condition == "revoked":
            approvals.decide(db, principal, institute, approvals.Request(operation_id=request.operation_id, operation_fingerprint=request.operation_fingerprint,
                previous_id=request.approval_id, previous_fingerprint=request.approval_fingerprint, decision="revoke", reason="Explicit move revocation", idempotency_key="revoke-move"))
        if condition == "expired":
            deadline = operations.Original.model_validate(operation.original).valid_until
            monkeypatch.setattr(executions, "utcnow", lambda: deadline+timedelta(seconds=1))
        if condition == "source_changed":
            update_appointment(db, operation.original["selection"]["appointment_id"], AppointmentUpdate(notes="Source edit"), "other-manager")
        with pytest.raises(HTTPException):
            executions.execute(db, principal, institute, request)
        assert not db.scalars(select(ExecutionOriginal)).all()
        assert explicit_utc_instant(db.get(Appointment, operation.original["selection"]["appointment_id"]).start_time) == operations.Original.model_validate(operation.original).preview.appointment.start_time
