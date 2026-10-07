from datetime import timedelta
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.revenue import slot_opportunities as slots
from app.modules.employees.models import Employee
from app.modules.services.models import Service
from app.modules.resources.models import Resource, ResourceRequirement, ServiceRequirement
from app.modules.appointments.models import Appointment
from app.modules.tickets.models import QueueTicket, TicketLine
from test_revenue_billing_14a import NOW
from test_workforce_absences_11b import setup
from test_ticket_workflow import _auth_headers
from test_postgres_scheduling_4d import postgres_flow


def exercise(engine, institute, employee, service, monkeypatch):
    monkeypatch.setattr(slots, "utcnow", lambda: NOW)
    horizon = NOW+timedelta(hours=2)
    with Session(engine) as db:
        for row in db.scalars(select(Employee).where(Employee.institute_id == institute)):
            row.status = "unavailable"
        chosen = db.get(Employee, employee); chosen.status = "available"; chosen.skills = []
        selected = db.get(Service, service); selected.duration_min = 20; selected.requires_machine = True
        db.commit()
        assert slots.read(db, institute, service, horizon).unavailable_reason == "resource_configuration_missing"
        selected.requires_machine = False
        db.add(ServiceRequirement(institute_id=institute, service_id=service, skill_code="revenue-proof-skill"))
        db.add(ResourceRequirement(id="revenue-room-need", institute_id=institute, service_id=service, kind="room", capability="", quantity=1))
        db.commit()
        assert slots.read(db, institute, service, horizon).unavailable_reason == "capacity_unknown"
        chosen.skills = ["revenue-proof-skill"]
        db.commit()
        assert slots.read(db, institute, service, horizon).unavailable_reason == "capacity_unknown"  # qualified staff, missing room
        db.add(Resource(id="revenue-room", institute_id=institute, name="Revenue proof room", kind="room", status="active", capabilities=[]))
        db.commit()
        empty = slots.read(db, institute, service, horizon)
        assert empty.opportunity.evidence.projected_start == NOW and empty.opportunity.evidence.employee_id == employee
        assert empty.opportunity.evidence.required_skills == ("revenue-proof-skill",)
        assert empty.opportunity.evidence.resource_needs[0].quantity == 1
        db.add(QueueTicket(id="revenue-prior", institute_id=institute, ticket_number="R", arrival_time=NOW, status="waiting"))
        db.flush()
        db.add(TicketLine(id="revenue-prior-line", ticket_id="revenue-prior", service_id=service, quantity=1, duration_minutes=20))
        db.commit()
        queued = slots.read(db, institute, service, horizon)
        assert queued.opportunity.evidence.projected_start == NOW+timedelta(minutes=20)
        assert queued.opportunity.evidence.prior_queue_count == 1
        db.add(Appointment(id="revenue-booking", institute_id=institute, employee_id=employee, service_id=service,
            customer_name="Fixture", start_time=NOW+timedelta(minutes=25), end_time=NOW+timedelta(minutes=60), status="confirmed"))
        db.commit()
        fitted = slots.read(db, institute, service, horizon)
        assert fitted.opportunity.evidence.projected_start == NOW+timedelta(minutes=60)
        assert fitted.opportunity.evidence.projected_end == NOW+timedelta(minutes=80)
        assert slots.read(db, institute, service, NOW+timedelta(minutes=60)).unavailable_reason == "outside_horizon"
        assert not fitted.opportunity.capacity_reserved and not fitted.opportunity.action_executed and fitted.opportunity.estimated_value is None
        for field in ("capacity_reserved", "action_executed"):
            with pytest.raises(ValueError): slots.Opportunity.model_validate({**fitted.opportunity.model_dump(), field: 0})
        chosen.skills = []; db.commit()
        assert slots.read(db, institute, service, horizon).unavailable_reason == "capacity_unknown"
        chosen.skills = ["revenue-proof-skill"]; db.commit()
        resource = db.get(Resource, "revenue-room"); resource.status = "maintenance"; db.commit()
        assert slots.read(db, institute, service, horizon).unavailable_reason == "capacity_unknown"
        resource.status = "active"; db.commit()
        with pytest.raises(HTTPException): slots.read(db, institute, service, NOW)
        with pytest.raises(HTTPException): slots.read(db, institute, "unknown", horizon)
        return fitted


def test_sqlite_sovereign_projection_and_signed_manager_read(client, monkeypatch):
    institute, employee, service, _, _ = setup(client)
    result = exercise(main_module.engine, institute, employee, service, monkeypatch)
    path = f"/api/v1/revenue/institutes/{institute}/capacity-opportunity"
    params = dict(service_id=service, horizon_end=result.horizon_end.isoformat())
    headers = _auth_headers("responsable_institut", institute)
    response = client.get(path, headers=headers, params=params)
    assert response.status_code == 200 and response.json()["opportunity"]["evidence"]["employee_id"] == employee
    for role, owner in (("accueil", institute), ("collaboratrice", institute), ("responsable_institut", "foreign")):
        assert client.get(path, headers=_auth_headers(role, owner), params=params).status_code == 403
    assert client.get(path, params=params).status_code == 403
    assert client.get(path, headers=headers, params={**params, "horizon_end": "2026-01-03"}).status_code == 422
    assert client.post(path, headers=headers, json=params).status_code == 405


def test_postgres_sovereign_projection(postgres_flow, monkeypatch):
    exercise(*postgres_flow, monkeypatch)
