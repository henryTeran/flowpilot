from datetime import timedelta
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
import app.main as main_module
from app.database.session import get_db
from app.modules.base import creation_capability as creation, sensitive_originals as operations, approvals, executions, creation_execution
from app.modules.base.read_capabilities import Principal
from app.modules.base.models import ExecutionOriginal
from app.modules.appointments.models import Appointment, BookingEvent
from app.modules.appointments.service import cancel_appointment
from app.modules.resources.models import Resource, ResourceRequirement, ResourceReservation
from app.modules.services.models import Service
from app.modules.waitlist.originals import fingerprint
from app.shared.time import utcnow
from test_ticket_workflow import _bootstrap_reference_data, _auth_headers
from test_postgres_scheduling_4d import postgres_flow, race


def authorized(flow, *, approve=True):
    engine, institute, employee, service = flow
    principal = Principal(actor_id="test-user", institute_id=institute, role="responsable_institut")
    with Session(engine) as db:
        db.get(Service, service).requires_machine = False
        db.add(Resource(id="execute-room", institute_id=institute, name="Execute room", kind="room", capabilities=[], status="active"))
        db.add(ResourceRequirement(id="execute-need", institute_id=institute, service_id=service, kind="room", capability="", quantity=1))
        db.commit()
        selection = dict(employee_id=employee, service_id=service, customer_name="Reviewed customer", phone="+33123456789",
            notes="Exact reviewed note", start_time=(utcnow()+timedelta(hours=3)).isoformat())
        preview = creation.preview(db, principal, institute, selection)
        operation = operations.create(db, principal, institute, operations.Request(capability="APPOINTMENT_CREATE", selection=selection,
            expected_state_fingerprint=preview.state_fingerprint, valid_until=utcnow()+timedelta(minutes=15),
            reason="Reviewed exact creation", idempotency_key="creation-operation"))
        approval = approvals.decide(db, principal, institute, approvals.Request(operation_id=operation.original["id"],
            operation_fingerprint=operation.fingerprint, previous_id=None, previous_fingerprint=None,
            decision="approve", reason="Explicit approved creation", idempotency_key="creation-approval")) if approve else None
    request = executions.Request(operation_id=operation.original["id"], operation_fingerprint=operation.fingerprint,
        approval_id=approval.original["id"] if approval else "missing-approval", approval_fingerprint=approval.fingerprint if approval else "0"*64,
        reason="Execute exact approved creation", idempotency_key="creation-execution")
    return principal, operation, request


def assert_effect(engine, expected):
    with Session(engine) as db:
        for model in (Appointment, BookingEvent, ResourceReservation, ExecutionOriginal):
            assert len(db.scalars(select(model)).all()) == expected


def exercise(client, flow, monkeypatch):
    engine, institute, *_ = flow
    principal, operation, request = authorized(flow)
    headers = _auth_headers("responsable_institut", institute)
    body = request.model_dump(mode="json")
    assert client.post("/api/v1/copilot/execute", headers=_auth_headers("accueil", institute), json=body).status_code == 403
    assert client.post("/api/v1/copilot/execute", headers=headers, json={**body, "approved": True}).status_code == 422
    with Session(engine) as db:
        db.get(Resource, "execute-room").status = "maintenance"
        db.commit()
        assert client.post("/api/v1/copilot/execute", headers=headers, json=body).status_code == 400
        db.get(Resource, "execute-room").status = "active"
        db.commit()
    assert_effect(engine, 0)
    assert client.post("/api/v1/copilot/execute", headers=headers, json={**body, "approval_fingerprint": "0"*64}).status_code == 400
    response = client.post("/api/v1/copilot/execute", headers=headers, json=body)
    assert response.status_code == 200, response.text
    receipt = response.json()
    assert receipt["fingerprint"] == fingerprint(receipt["original"])
    original = creation_execution.Original.model_validate(receipt["original"])
    assert original.before.resource_ids == ("execute-room",)
    assert original.after.status == "scheduled"
    assert original.saved_metadata_digest == fingerprint(creation_execution.metadata(original.before.selection))
    assert_effect(engine, 1)
    with Session(engine) as db:
        # Even recomputing both hashes cannot turn a pre-approval event into this execution.
        event = db.get(BookingEvent, original.booking_event_id)
        at = event.occurred_at
        row = db.scalar(select(ExecutionOriginal).where(ExecutionOriginal.operation_id == request.operation_id))
        event.occurred_at = original.before.captured_at-timedelta(seconds=1)
        altered = {**receipt["original"], "booking_event_fingerprint": fingerprint(executions.event_raw(event))}
        row.original, row.fingerprint = altered, fingerprint(altered)
        db.commit()
        with pytest.raises(HTTPException):
            executions.by_key(db, principal, institute, request.idempotency_key)
        db.rollback()
        event.occurred_at = at
        row.original, row.fingerprint = receipt["original"], receipt["fingerprint"]
        db.commit()
        appointment = db.get(Appointment, original.appointment_id)
        assert creation_execution.metadata(appointment) == creation_execution.metadata(original.before.selection)
        # A retained receipt proves its original effect, not today's booking status.
        cancel_appointment(db, appointment.id, "later-actor")
        assert executions.for_operation(db, principal, institute, request.operation_id).original == receipt["original"]
    monkeypatch.setattr(executions, "utcnow", lambda: original.created_at+timedelta(days=1))
    def no_effect(*args, **kwargs):
        raise AssertionError("Historical replay cannot revalidate or reserve")
    monkeypatch.setattr(creation, "preview", no_effect)
    monkeypatch.setattr(creation_execution, "create_appointment", no_effect)
    assert client.post("/api/v1/copilot/execute", headers=headers, json=body).json() == receipt
    assert client.post("/api/v1/copilot/execute", headers=headers, json={**body, "idempotency_key": "new-key"}).status_code == 400
    with Session(engine) as db:
        assert executions.by_key(db, principal, institute, request.idempotency_key).original == receipt["original"]
        changed = {**operation.original, "preview": {**operation.original["preview"], "capability": {
            **operation.original["preview"]["capability"], "execution_registered": False}}}
        assert operations.Original.model_validate(changed).preview.capability.execution_registered is False
    discovered = client.get("/api/v1/copilot/execution-capabilities", headers=headers)
    assert discovered.status_code == 200 and discovered.json()[0]["name"] == "APPOINTMENT_CREATE"


def test_sqlite_signed_atomic_creation_and_historical_replay(client, monkeypatch):
    institute, employees, services = _bootstrap_reference_data(client)
    exercise(client, (main_module.engine, institute, employees[0]["id"], services[0]["id"]), monkeypatch)


def test_postgres_signed_atomic_creation_and_historical_replay(client, postgres_flow, monkeypatch):
    engine, *_ = postgres_flow
    def database():
        with Session(engine) as db:
            yield db
    main_module.app.dependency_overrides[get_db] = database
    monkeypatch.setattr(main_module, "engine", engine)
    exercise(client, postgres_flow, monkeypatch)


def test_postgres_creation_rollback_and_lost_ack_recovery(postgres_flow, monkeypatch):
    engine, institute, *_ = postgres_flow
    principal, operation, request = authorized(postgres_flow)
    verify = executions.verify
    def fail(*args):
        raise RuntimeError("Injected receipt failure after domain writes")
    monkeypatch.setattr(executions, "verify", fail)
    with Session(engine) as db:
        with pytest.raises(RuntimeError):
            executions.execute(db, principal, institute, request)
    assert_effect(engine, 0)
    monkeypatch.setattr(executions, "verify", verify)
    with Session(engine) as db:
        commit = db.commit
        def lost_ack():
            commit()
            raise RuntimeError("Injected acknowledgement loss after commit")
        monkeypatch.setattr(db, "commit", lost_ack)
        with pytest.raises(RuntimeError):
            executions.execute(db, principal, institute, request)
    assert_effect(engine, 1)
    with Session(engine) as db:
        assert executions.execute(db, principal, institute, request) == executions.by_key(db, principal, institute, request.idempotency_key)
    assert_effect(engine, 1)


@pytest.mark.parametrize("same_key", [True, False])
def test_postgres_competing_creation_executions_have_one_effect(postgres_flow, same_key):
    engine, institute, *_ = postgres_flow
    principal, operation, request = authorized(postgres_flow)
    other = request if same_key else request.model_copy(update={"idempotency_key": "competing-key"})
    results = race(engine, [lambda db: executions.execute(db, principal, institute, request).original and db.scalar(select(Appointment)),
        lambda db: executions.execute(db, principal, institute, other).original and db.scalar(select(Appointment))])
    assert sorted(status for status, _ in results) == (["ok", "ok"] if same_key else ["conflict", "ok"])
    assert_effect(engine, 1)


@pytest.mark.parametrize("condition", ["pending", "revoked", "expired"])
def test_creation_without_current_valid_approval_never_books(client, monkeypatch, condition):
    institute, employees, services = _bootstrap_reference_data(client)
    principal, operation, request = authorized((main_module.engine, institute, employees[0]["id"], services[0]["id"]),
        approve=condition != "pending")
    with Session(main_module.engine) as db:
        if condition == "revoked":
            approvals.decide(db, principal, institute, approvals.Request(operation_id=request.operation_id,
                operation_fingerprint=request.operation_fingerprint, previous_id=request.approval_id,
                previous_fingerprint=request.approval_fingerprint, decision="revoke", reason="Explicit revocation", idempotency_key="revoke-creation"))
        if condition == "expired":
            deadline = operations.Original.model_validate(operation.original).valid_until
            monkeypatch.setattr(executions, "utcnow", lambda: deadline+timedelta(seconds=1))
        with pytest.raises(HTTPException):
            executions.execute(db, principal, institute, request)
    assert_effect(main_module.engine, 0)
