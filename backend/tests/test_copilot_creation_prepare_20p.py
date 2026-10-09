from datetime import timedelta
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
import app.main as main_module
from app.database.session import get_db
from app.modules.appointments.models import Appointment, BookingEvent
from app.modules.resources.models import ResourceReservation
from app.modules.services.models import Service
from app.modules.base.models import SensitiveOperationOriginal, ApprovalOriginal
from app.modules.base import creation_capability as creation, sensitive_originals as operations
from app.modules.waitlist.originals import fingerprint
from app.shared.time import utcnow
from test_ticket_workflow import _bootstrap_reference_data, _auth_headers
from test_postgres_scheduling_4d import postgres_flow


def exercise(client, engine, institute, employee, service):
    headers = _auth_headers("responsable_institut", institute)
    selection = dict(employee_id=employee, service_id=service, customer_name="Reviewed customer",
        start_time=(utcnow()+timedelta(hours=3)).isoformat())
    request = {"message": "Preparer la creation d'un rendez-vous", "ui_context": selection}
    def preview(body=request, role="responsable_institut"):
        return client.post("/api/v1/copilot/prepare-preview", headers=_auth_headers(role, institute), json=body)
    response = preview()
    assert response.status_code == 200, response.text
    value = response.json()
    assert value["effect"] == "creation_preview_only_no_reservation_approval_or_execution"
    assert value["principal"]["institute_id"] == institute
    preparation = dict(capability="APPOINTMENT_CREATE", selection=selection, expected_state_fingerprint=value["state_fingerprint"],
        valid_until=(utcnow()+timedelta(minutes=15)).isoformat(), reason="Reviewed exact appointment creation", idempotency_key="creation-prepare")
    def prepare(operation=preparation, message=request["message"]):
        return client.post("/api/v1/copilot/prepare", headers=headers, json={"message": message, "operation": operation})
    response = prepare()
    assert response.status_code == 200, response.text
    receipt = response.json()
    assert receipt["fingerprint"] == fingerprint(receipt["original"])
    assert receipt["original"]["selection"] == value["selection"]
    assert prepare().json() == receipt
    assert prepare({**preparation, "selection": {**selection, "customer_name": "Substituted customer"}}).status_code == 400
    assert prepare({**preparation, "idempotency_key": "forged-source", "expected_state_fingerprint": "0"*64}).status_code == 400
    assert prepare(message="Consulter la fiche de la cliente").status_code == 400
    assert preview(role="accueil").status_code == 403
    assert preview({**request, "ui_context": {**selection, "start_time": 1}}).status_code == 422
    assert preview({**request, "ui_context": {**selection, "institute_id": "foreign"}}).status_code == 422
    assert preview({**request, "ui_context": {**selection, "employee_id": "missing"}}).status_code == 404
    base = f"/api/v1/base/institutes/{institute}"
    operation_id = receipt["original"]["id"]
    state = client.get(f"{base}/sensitive-operations/{operation_id}/approval-state", headers=headers)
    assert state.status_code == 200 and state.json()["status"] == "pending"
    decision = dict(operation_id=operation_id, operation_fingerprint=receipt["fingerprint"], previous_id=None,
        previous_fingerprint=None, decision="approve", reason="Explicit reviewed approval", idempotency_key="creation-approval")
    with Session(engine) as db:
        selected = db.get(Service, service)
        previous_duration = selected.duration_min, selected.duration_max
        selected.duration_min = selected.duration_max = (selected.duration_max or selected.duration_min)+5
        db.commit()
        assert client.post(f"{base}/approvals", headers=headers, json=decision).status_code == 400
        selected.duration_min, selected.duration_max = previous_duration
        db.commit()
    approved = client.post(f"{base}/approvals", headers=headers, json=decision)
    assert approved.status_code == 200, approved.text
    approval = approved.json()
    assert approval["original"]["decision"] == "approve"
    with Session(engine) as db:
        assert len(db.scalars(select(SensitiveOperationOriginal)).all()) == len(db.scalars(select(ApprovalOriginal)).all()) == 1
        for model in (Appointment, BookingEvent, ResourceReservation):
            assert not db.scalars(select(model)).all()
    discovered = client.get("/api/v1/copilot/preparation-capabilities", headers=headers)
    assert discovered.status_code == 200 and discovered.json()[0]["level"] == 2
    assert client.get("/api/v1/copilot/preparation-capabilities", headers=_auth_headers("accueil", institute)).status_code == 403
    raw = value.copy()
    raw["selection"] = {**raw["selection"], "customer_name": "Tampered terms"}
    with pytest.raises(ValueError):
        creation.Preview.model_validate(raw)
    with pytest.raises(ValueError):
        operations.Original.model_validate({**receipt["original"], "selection": {
            **receipt["original"]["selection"], "customer_name": "Substituted retained terms"}})
    with pytest.raises(ValueError):
        operations.Request.model_validate({**preparation, "capability": "APPOINTMENT_CANCEL"})


def test_sqlite_official_base_creation_preparation_and_approval(client):
    institute, employees, services = _bootstrap_reference_data(client)
    exercise(client, main_module.engine, institute, employees[0]["id"], services[0]["id"])


def test_postgres_official_base_creation_preparation_and_approval(client, postgres_flow, monkeypatch):
    engine, institute, employee, service = postgres_flow
    def database():
        with Session(engine) as db:
            yield db
    main_module.app.dependency_overrides[get_db] = database
    monkeypatch.setattr(main_module, "engine", engine)
    exercise(client, engine, institute, employee, service)
