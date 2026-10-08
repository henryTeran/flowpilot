from datetime import timedelta
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.base import sensitive_capabilities as sensitive, read_capabilities as base
from app.modules.appointments.models import Appointment, BookingEvent
from app.modules.appointments.schemas import AppointmentCreate, AppointmentUpdate
from app.modules.appointments.service import create_appointment, update_appointment, cancel_appointment, require_cancellable
from app.modules.resources.models import ResourceReservation
from app.shared.time import utcnow
from test_ticket_workflow import _auth_headers, _bootstrap_reference_data
from test_postgres_scheduling_4d import postgres_flow
from test_postgres_resources_5b import shared_room


@pytest.mark.parametrize("status", ["scheduled", "confirmed", "arrived", "in_progress", "completed", "cancelled", "no_show", "unknown"])
def test_shared_cancellation_rule(status):
    if status in {"scheduled", "confirmed", "arrived"}: require_cancellable(SimpleNamespace(status=status))
    else:
        with pytest.raises(HTTPException) as error: require_cancellable(SimpleNamespace(status=status))
        assert error.value.status_code == 400


def exercise(engine, institute, employee, service):
    principal = base.Principal(actor_id="signed-manager", institute_id=institute, role="responsable_institut")
    with Session(engine) as db:
        appointment = create_appointment(db, AppointmentCreate(institute_id=institute, employee_id=employee,
            service_id=service, customer_name="Private test name", phone="private-phone", notes="private-note",
            start_time=utcnow()+timedelta(hours=1)), principal.actor_id)
        identifier = appointment.id
        reservation = db.scalar(select(ResourceReservation).where(ResourceReservation.appointment_id == identifier))
        assert reservation.status == "reserved"
        events = db.scalar(select(func.count()).select_from(BookingEvent))
        preview = sensitive.preview(db, principal, institute, {"appointment_id": identifier})
        assert preview.effect == "cancellation_preview_only_no_approval_or_execution"
        assert preview.capability.prepare_level == 2 and preview.capability.execution_level == 3
        assert preview.capability.public_execution is False
        assert not any(field in preview.appointment for field in ("customer_name", "phone", "notes"))
        assert all(private not in preview.model_dump_json() for private in ("Private test name", "private-phone", "private-note"))
        assert sensitive.preview(db, principal, institute, {"appointment_id": identifier}).state_fingerprint == preview.state_fingerprint
        assert db.scalar(select(func.count()).select_from(BookingEvent)) == events
        assert appointment.status == "scheduled" and reservation.status == "reserved"
        db.rollback()
        # Same operational snapshot but a new booking event still invalidates the reference.
        update_appointment(db, identifier, AppointmentUpdate(notes="changed-private-note"), principal.actor_id)
        changed = sensitive.preview(db, principal, institute, {"appointment_id": identifier})
        assert changed.appointment == preview.appointment
        assert changed.booking_events == preview.booking_events + 1
        assert changed.state_fingerprint != preview.state_fingerprint
        assert changed.booking_history_fingerprint != preview.booking_history_fingerprint
        db.rollback()
        before = db.scalar(select(func.count()).select_from(BookingEvent))
        cancelled = cancel_appointment(db, identifier, principal.actor_id, commit=False)
        assert cancelled.status == "cancelled"
        assert db.scalar(select(ResourceReservation).where(ResourceReservation.appointment_id == identifier)).status == "released"
        assert db.scalar(select(func.count()).select_from(BookingEvent)) == before+1
        db.rollback()
        assert db.get(Appointment, identifier).status == "scheduled"
        assert db.scalar(select(ResourceReservation).where(ResourceReservation.appointment_id == identifier)).status == "reserved"
        assert db.scalar(select(func.count()).select_from(BookingEvent)) == before
        cancel_appointment(db, identifier, principal.actor_id, commit=False)
        db.commit()
    with Session(engine) as db:
        assert db.get(Appointment, identifier).status == "cancelled"
        assert db.scalar(select(ResourceReservation).where(ResourceReservation.appointment_id == identifier)).status == "released"
        rows = db.scalars(select(BookingEvent).where(BookingEvent.appointment_id == identifier, BookingEvent.event_type == "cancelled")).all()
        assert len(rows) == 1 and rows[0].actor_id == principal.actor_id
        with pytest.raises(HTTPException): sensitive.preview(db, principal, institute, {"appointment_id": identifier})
    return identifier


def test_sqlite_preview_and_caller_owned_atomic_cancel(client):
    institute, employees, services = _bootstrap_reference_data(client)
    headers = _auth_headers("responsable_institut", institute)
    prefix = f"/api/v1/resources/institutes/{institute}"
    assert client.patch(prefix+f"/services/{services[0]['id']}/requirements", json={"skills": [], "resources": [{"kind": "room"}]}, headers=headers).status_code == 200
    assert client.post(prefix, json={"name": "Preview room", "kind": "room"}, headers=headers).status_code == 200
    exercise(main_module.engine, institute, employees[0]["id"], services[0]["id"])


def test_actual_postgres_preview_and_caller_owned_atomic_cancel(postgres_flow):
    shared_room(postgres_flow)
    exercise(*postgres_flow)


def test_signed_preview_is_scoped_strict_and_cannot_execute(client):
    institute, employees, services = _bootstrap_reference_data(client)
    headers = _auth_headers("responsable_institut", institute)
    booking = client.post("/api/v1/appointments", headers=headers, json={"institute_id": institute,
        "employee_id": employees[0]["id"], "service_id": services[0]["id"], "customer_name": "Private name",
        "start_time": (utcnow()+timedelta(hours=1)).isoformat()})
    assert booking.status_code == 200, booking.text
    identifier = booking.json()["id"]
    prefix = f"/api/v1/base/institutes/{institute}"
    path = prefix+"/sensitive-previews/appointment-cancel"
    body = {"appointment_id": identifier}
    response = client.post(path, json=body, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["principal"]["actor_id"] == "test-user"
    assert response.json()["appointment"]["status"] == "scheduled"
    discovery = client.get(prefix+"/sensitive-capabilities", headers=headers)
    assert discovery.status_code == 200 and discovery.json()[0]["public_execution"] is False
    for role, owner in [("accueil", institute), ("collaboratrice", institute), ("direction", institute), ("super_admin", institute), ("responsable_institut", "foreign")]:
        denied = _auth_headers(role, owner)
        assert client.post(path, json=body, headers=denied).status_code == 403
        assert client.get(prefix+"/sensitive-capabilities", headers=denied).status_code == 403
    assert client.post(path, json=body).status_code == 403
    for field in ("approved", "actor_id", "institute_id", "state_fingerprint", "appointment", "commit", "sql"):
        assert client.post(path, json={**body, field: "injected"}, headers=headers).status_code == 422
    assert client.post(path, json={"appointment_id": "missing"}, headers=headers).status_code == 404
    assert client.post(prefix+"/reads", json={"capability": "APPOINTMENT_CANCEL", "arguments": body}, headers=headers).status_code == 422
    with Session(main_module.engine) as db:
        assert db.get(Appointment, identifier).status == "scheduled"
        assert db.scalar(select(func.count()).select_from(BookingEvent)) == 1
    # A signed foreign institute cannot capture another institute's appointment.
    with Session(main_module.engine) as db:
        from app.modules.institutes.models import Institute
        owner = db.get(Institute, institute)
        foreign = "cancellation-foreign"
        db.add(Institute(id=foreign, region_id=owner.region_id, name="Foreign", city="Foreign", timezone="Europe/Paris"))
        db.commit()
    assert client.post(f"/api/v1/base/institutes/{foreign}/sensitive-previews/appointment-cancel", json=body,
        headers=_auth_headers("responsable_institut", foreign)).status_code == 404
    # Corrupt cross-tenant employee references cannot change another institute's staff.
    with Session(main_module.engine) as db:
        from app.modules.employees.models import Employee
        employee = db.get(Employee, employees[0]["id"])
        employee.institute_id = foreign; db.commit()
    assert client.post(path, json=body, headers=headers).status_code == 400
    assert client.patch(f"/api/v1/appointments/{identifier}/cancel", headers=headers).status_code == 400
    with Session(main_module.engine) as db:
        assert db.get(Appointment, identifier).status == "scheduled"
        assert db.scalar(select(func.count()).select_from(BookingEvent)) == 1


def test_unsafe_selection_and_transaction_mode_reject_before_read(monkeypatch):
    principal = base.Principal(actor_id="signed", institute_id="scope", role="responsable_institut")
    def forbidden(*args): raise AssertionError("Invalid selection must not query")
    monkeypatch.setattr(sensitive, "lock_institute", forbidden)
    bad = sensitive.Selection(appointment_id="selected").model_copy(update={"appointment_id": 3})
    with pytest.raises(HTTPException): sensitive.preview(None, principal, "scope", bad)
    for commit in (0, 1, "false", None):
        with pytest.raises(HTTPException): cancel_appointment(None, "selected", commit=commit)


def cached_ownership_exercise(engine, institute, employee, service):
    from app.modules.employees.models import Employee
    from app.modules.institutes.models import Institute
    principal = base.Principal(actor_id="signed", institute_id=institute, role="responsable_institut")
    with Session(engine) as db:
        appointment = create_appointment(db, AppointmentCreate(institute_id=institute, employee_id=employee,
            service_id=service, customer_name="Test", start_time=utcnow()+timedelta(hours=1)))
        identifier = appointment.id
        owner = db.get(Institute, institute)
        db.add(Institute(id="cached-foreign", region_id=owner.region_id, name="Foreign", city="Foreign", timezone="Europe/Paris"))
        db.commit()
    with Session(engine) as db:
        cached = db.get(Employee, employee)
        with Session(engine) as peer:
            moved = peer.get(Employee, employee); moved.institute_id = "cached-foreign"; peer.commit()
        assert cached.institute_id == institute  # Actual stale identity-map value.
        with pytest.raises(HTTPException) as error:
            sensitive.preview(db, principal, institute, {"appointment_id": identifier})
        assert error.value.status_code == 400
        with pytest.raises(HTTPException): cancel_appointment(db, identifier, principal.actor_id, commit=False)
        db.rollback()
    with Session(engine) as db:
        assert db.get(Appointment, identifier).status == "scheduled"
        assert db.scalar(select(func.count()).select_from(BookingEvent)) == 1


def test_sqlite_cached_employee_ownership_cannot_authorize_cancellation(client):
    institute, employees, services = _bootstrap_reference_data(client)
    cached_ownership_exercise(main_module.engine, institute, employees[0]["id"], services[0]["id"])


def test_actual_postgres_cached_employee_ownership_cannot_authorize_cancellation(postgres_flow):
    cached_ownership_exercise(*postgres_flow)
