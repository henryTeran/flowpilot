from datetime import timedelta
import pytest
from sqlalchemy import event, select
from sqlalchemy.orm import Session
import app.main as main_module
from app.database.session import get_db
from app.modules.appointments import service as appointments
from app.modules.appointments.schemas import AppointmentCreate, AppointmentUpdate
from app.modules.appointments.events import snapshot
from app.modules.appointments.models import Appointment, BookingEvent
from app.modules.resources.models import Resource, ResourceRequirement, ResourceReservation
from app.modules.services.models import Service
from app.modules.base import move_capability as move, sensitive_originals as operations
from app.modules.base.models import SensitiveOperationOriginal, ApprovalOriginal
from app.modules.waitlist.originals import fingerprint
from app.shared.time import utcnow, explicit_utc_instant
from test_postgres_scheduling_4d import postgres_flow
from test_ticket_workflow import _bootstrap_reference_data, _auth_headers


def exercise(client, engine, institute, employee, service):
    now = utcnow()
    with Session(engine) as db:
        db.get(Service, service).requires_machine = False
        db.add(Resource(id="move-prepare-room", institute_id=institute, name="Move prepare room", kind="room", capabilities=[], status="active"))
        db.add(ResourceRequirement(id="move-prepare-need", institute_id=institute, service_id=service, kind="room", capability="", quantity=1))
        db.commit()
        booked = appointments.create_appointment(db, AppointmentCreate(institute_id=institute, employee_id=employee,
            service_id=service, customer_name="Private source name", phone="+33123456789", notes="Private source note", start_time=now+timedelta(hours=2)))
        identifier = booked.id
        source_start = explicit_utc_instant(booked.start_time)
    headers = _auth_headers("responsable_institut", institute)
    message = "Preparer le deplacement d'un rendez-vous"
    selection = dict(appointment_id=identifier, start_time=(source_start+timedelta(minutes=1)).isoformat())
    def preview(ui=selection, text=message, role="responsable_institut"):
        return client.post("/api/v1/copilot/prepare-preview/move", headers=_auth_headers(role, institute), json={"message": text, "ui_context": ui})
    statements = []
    def collect(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lstrip().split()[0].upper())
    event.listen(engine, "before_cursor_execute", collect)
    try:
        response = preview()
        assert response.status_code == 200, response.text
        value = response.json()
        assert value["resource_ids"] == ["move-prepare-room"] and value["booking_events"] == 1
        assert value["effect"] == "move_preview_only_no_reservation_approval_or_execution"
        for field in ("Private source", '"phone"', '"notes"', '"actor_id": "private"'):
            assert field not in response.text
    finally:
        event.remove(engine, "before_cursor_execute", collect)
    assert not set(statements) & {"INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER"}
    operation = dict(capability="APPOINTMENT_MOVE", selection=selection, expected_state_fingerprint=value["state_fingerprint"],
        valid_until=(utcnow()+timedelta(minutes=15)).isoformat(), reason="Reviewed exact move", idempotency_key="move-preparation")
    def prepare(body=operation, text=message):
        return client.post("/api/v1/copilot/prepare", headers=headers, json={"message": text, "operation": body})
    prepared = prepare()
    assert prepared.status_code == 200, prepared.text
    receipt = prepared.json()
    assert receipt["fingerprint"] == fingerprint(receipt["original"])
    assert prepare().json() == receipt
    assert preview(role="accueil").status_code == 403
    assert preview({**selection, "start_time": 1}).status_code == 422
    assert preview({**selection, "phone": "injected"}).status_code == 422
    assert preview({**selection, "appointment_id": "missing"}).status_code == 404
    assert preview({**selection, "start_time": source_start.isoformat()}).status_code == 400
    assert prepare(text="Preparer la creation d'un rendez-vous").status_code == 400
    assert prepare({**operation, "expected_state_fingerprint": "0"*64, "idempotency_key": "forged-state"}).status_code == 400
    with Session(engine) as db:
        db.get(Appointment, identifier).actual_start_time = now
        db.commit()
        assert preview().status_code == 400  # contradictory source execution terms are not a movable booking
        db.get(Appointment, identifier).actual_start_time = None
        db.commit()
    assert preview().status_code == 200
    base = f"/api/v1/base/institutes/{institute}"
    decision = dict(operation_id=receipt["original"]["id"], operation_fingerprint=receipt["fingerprint"], previous_id=None,
        previous_fingerprint=None, decision="approve", reason="Explicit move approval", idempotency_key="move-approval")
    with Session(engine) as db:
        # Metadata-only source edits change the booking history, even with the same slot.
        appointments.update_appointment(db, identifier, AppointmentUpdate(notes="Source changed"), "other-manager")
    assert client.post(f"{base}/approvals", headers=headers, json=decision).status_code == 400
    refreshed = preview().json()
    assert refreshed["booking_events"] == 2 and refreshed["state_fingerprint"] != value["state_fingerprint"]
    replacement = {**operation, "expected_state_fingerprint": refreshed["state_fingerprint"], "idempotency_key": "fresh-move"}
    retained = prepare(replacement).json()
    decision = {**decision, "operation_id": retained["original"]["id"], "operation_fingerprint": retained["fingerprint"]}
    approval = client.post(f"{base}/approvals", headers=headers, json=decision)
    assert approval.status_code == 200, approval.text
    approved = approval.json()
    request = dict(operation_id=decision["operation_id"], operation_fingerprint=decision["operation_fingerprint"],
        approval_id=approved["original"]["id"], approval_fingerprint=approved["fingerprint"], reason="Unsupported move execution", idempotency_key="move-execution")
    assert client.post("/api/v1/copilot/execute", headers=headers, json=request).status_code == 400
    assert client.post(f"{base}/executions", headers=headers, json=request).status_code == 400
    with Session(engine) as db:
        assert explicit_utc_instant(db.get(Appointment, identifier).start_time) == source_start
        assert len(db.scalars(select(BookingEvent)).all()) == 2  # only creation and explicit metadata edit
        assert len(db.scalars(select(ResourceReservation)).all()) == 1
        assert len(db.scalars(select(SensitiveOperationOriginal)).all()) == 2
        assert len(db.scalars(select(ApprovalOriginal)).all()) == 1
    with pytest.raises(ValueError):
        operations.Original.model_validate({**retained["original"], "selection": {**retained["original"]["selection"], "employee_id": "substituted"}})
    with pytest.raises(ValueError):
        move.Preview.model_validate({**refreshed, "state_fingerprint": "0"*64})
    discovery = client.get("/api/v1/copilot/preparation-capabilities", headers=headers)
    assert discovery.status_code == 200 and {row["name"] for row in discovery.json()} == {"APPOINTMENT_CREATE", "APPOINTMENT_MOVE"}
    capabilities = {row["name"]: row for row in discovery.json()}
    assert capabilities["APPOINTMENT_CREATE"]["input_schema"]["$defs"]["OperationRequest"]["properties"]["capability"]["const"] == "APPOINTMENT_CREATE"
    assert capabilities["APPOINTMENT_MOVE"]["input_schema"]["$defs"]["MoveOperationRequest"]["properties"]["capability"]["const"] == "APPOINTMENT_MOVE"


def test_sqlite_official_base_move_retention_and_approval(client):
    institute, employees, services = _bootstrap_reference_data(client)
    exercise(client, main_module.engine, institute, employees[0]["id"], services[0]["id"])


def test_postgres_official_base_move_retention_and_approval(client, postgres_flow, monkeypatch):
    engine, institute, employee, service = postgres_flow
    def database():
        with Session(engine) as db:
            yield db
    main_module.app.dependency_overrides[get_db] = database
    monkeypatch.setattr(main_module, "engine", engine)
    exercise(client, engine, institute, employee, service)
