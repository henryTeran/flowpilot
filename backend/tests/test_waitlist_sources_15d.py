from datetime import timedelta
import pytest
from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.waitlist import originals, lifecycle, sources
from app.modules.waitlist.models import DemandOriginal, LifecycleOriginal
from app.modules.appointments.models import Appointment
from app.modules.employees.models import Employee
from app.modules.services.models import Service
from app.modules.resources.models import Resource, ResourceRequirement, ResourceReservation, ServiceRequirement
from app.modules.crm import lifecycle_originals
from app.modules.crm.lifecycle import LifecycleDeclaration, CommunicationDeclaration
from app.modules.tickets.models import QueueTicket, TicketLine
from app.modules.planning.models import ServiceSession
from app.modules.workforce.models import EmployeeAbsence
from test_waitlist_originals_15b import prepare, request
from test_waitlist_lifecycle_15c import transition
from test_waitlist_matching_15a import NOW
from test_workforce_absences_11b import setup
from test_ticket_workflow import _auth_headers
from test_postgres_scheduling_4d import postgres_flow


def permission(institute, permission, key, previous=None):
    communications = tuple(CommunicationDeclaration(channel=channel, purpose=purpose,
        permission=permission if (channel, purpose) == ("email", "service_follow_up") else "unknown",
        evidence="Déclaration explicite de cliente" if (channel, purpose) == ("email", "service_follow_up") and permission != "unknown" else None)
        for channel in ("email", "sms") for purpose in ("service_follow_up", "marketing"))
    return lifecycle_originals.Declaration(declaration=LifecycleDeclaration(institute_id=institute, customer_id="waitlist-customer",
        birthday=None, birthday_evidence=None, communications=communications), previous_id=previous,
        reason="Consentement relu avec cliente", idempotency_key=key)


def prepare_sources(engine, institute, employee, service, monkeypatch):
    prepare(engine, institute, service)
    for module in (originals, lifecycle, sources, lifecycle_originals):
        monkeypatch.setattr(module, "utcnow", lambda: NOW)
    with Session(engine) as db:
        for row in db.scalars(select(Employee).where(Employee.institute_id == institute)):
            row.status = "unavailable"
        row = db.get(Employee, employee); row.status = "available"; row.skills = ["waitlist-care"]
        db.add(ServiceRequirement(institute_id=institute, service_id=service, skill_code="waitlist-care"))
        db.add(Resource(id="waitlist-room", institute_id=institute, name="Waitlist room", kind="room", capabilities=["care"], status="active"))
        db.add(ResourceRequirement(id="waitlist-need", institute_id=institute, service_id=service, kind="room", capability="care", quantity=1))
        db.commit()
        root = originals.create(db, institute, request(service, employee), "signed")
        activated = lifecycle.create(db, institute, transition(root), "signed")
        return root, activated


def read(db, institute, root, event, **changes):
    values = dict(channel="email", history_requirement="review_only", permission_requirement="review_only")
    values.update(changes)
    return sources.read(db, institute, root.original["id"], event.original["id"], event.fingerprint,
        NOW+timedelta(hours=3), sources.Policy(**values))


def exercise(engine, institute, employee, service, monkeypatch):
    root, activated = prepare_sources(engine, institute, employee, service, monkeypatch)
    with Session(engine) as db:
        base = read(db, institute, root, activated)
        assert base.review.options[0].start == NOW+timedelta(hours=1)
        assert base.review.options[0].resource_ids == ("waitlist-room",)
        assert base.review.capture.customer.history == "no_recorded_care"
        assert base.review.capture.customer.permission == "unknown"
        assert base.evidence.opening_hours == "not_verified" and base.evidence.contact_authority == "not_granted_by_this_read"
        assert read(db, institute, root, activated, history_requirement="observed_care_required").unavailable_reason == "history_requirement_unmet"
        assert read(db, institute, root, activated, permission_requirement="recorded_grant_required").unavailable_reason == "permission_requirement_unmet"
        granted = lifecycle_originals.create(db, institute, "waitlist-customer", permission(institute, "granted", "grant"), "signed")
        assert read(db, institute, root, activated, permission_requirement="recorded_grant_required").review is not None
        refused = lifecycle_originals.create(db, institute, "waitlist-customer", permission(institute, "refused", "refuse", granted.id), "signed")
        assert read(db, institute, root, activated, permission_requirement="recorded_grant_required").review is None
        monkeypatch.setattr(lifecycle_originals, "utcnow", lambda: NOW+timedelta(days=1))
        lifecycle_originals.create(db, institute, "waitlist-customer", permission(institute, "granted", "future", refused.id), "signed")
        future = read(db, institute, root, activated)
        assert future.evidence.permission_reason == "future_declaration" and future.review.capture.customer.permission == "unknown"
        # A customer's existing return blocks even another employee's slot.
        db.add(Appointment(id="waitlist-existing", institute_id=institute, employee_id=employee, service_id=service,
            customer_id="waitlist-customer", customer_name="Fixture", start_time=NOW+timedelta(hours=1),
            end_time=NOW+timedelta(hours=1, minutes=40), status="confirmed"))
        db.commit()
        blocked = read(db, institute, root, activated)
        assert not blocked.review.options  # only20 minutes remain in customer declaration
        db.get(Appointment, "waitlist-existing").end_time = NOW+timedelta(hours=1, minutes=30); db.commit()
        assert read(db, institute, root, activated).review.options[0].start == NOW+timedelta(hours=1, minutes=30)
        db.delete(db.get(Appointment, "waitlist-existing")); db.commit()
        db.get(Resource, "waitlist-room").status = "maintenance"; db.commit()
        assert not read(db, institute, root, activated).review.options
        db.get(Resource, "waitlist-room").status = "active"
        db.get(Employee, employee).skills = []; db.commit()
        assert not read(db, institute, root, activated).review.options
        db.get(Employee, employee).skills = ["waitlist-care"]
        db.get(Service, service).duration_min = 31; db.commit()
        assert read(db, institute, root, activated).review.unavailable_reason == "duration_changed"
        db.get(Service, service).duration_min = 30; db.commit()
        assert db.scalar(select(func.count()).select_from(DemandOriginal)) == 1
        assert db.scalar(select(func.count()).select_from(LifecycleOriginal)) == 1
        assert db.scalar(select(func.count()).select_from(ResourceReservation)) == 0
    return root, activated


def test_sqlite_current_sources_and_signed_read(client, monkeypatch):
    institute, employee, service, _, _ = setup(client)
    root, activated = exercise(main_module.engine, institute, employee, service, monkeypatch)
    path = f"/api/v1/waitlist/institutes/{institute}/lifecycle/states/{root.original['id']}/matching"
    params = dict(expected_event_id=activated.original["id"], expected_event_fingerprint=activated.fingerprint,
        horizon_end=(NOW+timedelta(hours=3)).isoformat(), channel="email", history_requirement="review_only", permission_requirement="review_only")
    headers = _auth_headers("responsable_institut", institute)
    response = client.get(path, headers=headers, params=params)
    assert response.status_code == 200, response.text
    assert response.json()["review"]["options"]
    for role, owner in (("accueil", institute), ("collaboratrice", institute), ("responsable_institut", "foreign")):
        assert client.get(path, params=params, headers=_auth_headers(role, owner)).status_code == 403
    assert client.get(path, params=params).status_code == 403
    assert client.post(path, headers=headers, json=params).status_code == 405
    assert client.get(path, headers=headers, params={**params, "horizon_end": "2026-10-09"}).status_code == 422
    assert client.get(path, headers=headers, params={**params, "horizon_end": str(int((NOW+timedelta(hours=3)).timestamp()))}).status_code == 422
    assert client.get(path, headers=headers, params={**params, "expected_event_fingerprint": "0"*64}).status_code == 400


def test_actual_postgres_current_sources(postgres_flow, monkeypatch):
    exercise(*postgres_flow, monkeypatch)


def test_recorded_care_context_and_invalid_completed_source(client, monkeypatch):
    institute, employee, service, _, _ = setup(client)
    root, activated = prepare_sources(main_module.engine, institute, employee, service, monkeypatch)
    with Session(main_module.engine) as db:
        db.add(QueueTicket(id="waitlist-care", institute_id=institute, customer_id="waitlist-customer", ticket_number="W",
            status="paid", arrival_time=NOW-timedelta(days=1), paid_at=NOW-timedelta(hours=23)))
        db.flush()
        db.add(TicketLine(id="waitlist-line", ticket_id="waitlist-care", service_id=service, quantity=1, duration_minutes=30))
        db.flush()
        db.add(ServiceSession(id="waitlist-completed", institute_id=institute, employee_id=employee, service_id=service,
            ticket_line_id="waitlist-line", start_time=NOW-timedelta(days=1), planned_end_time=NOW-timedelta(days=1, minutes=-30),
            real_end_time=NOW-timedelta(days=1, minutes=-30), duration_minutes=30, status="completed"))
        db.commit()
        result = read(db, institute, root, activated, history_requirement="observed_care_required")
        assert result.review.capture.customer.history_reference == "waitlist-care"
        assert result.evidence.observed_care_episodes == 1
        assert read(db, institute, root, activated, history_requirement="no_recorded_care_required").review is None
        db.get(ServiceSession, "waitlist-completed").real_end_time = None; db.commit()
        result = read(db, institute, root, activated)
        assert result.review.capture.customer.history == "unknown" and result.evidence.care_diagnostics["invalid_actual_times"] == 1
        assert read(db, institute, root, activated, history_requirement="observed_care_required").review is None


def test_cancelled_stale_versions_and_malformed_active_cohort(client, monkeypatch):
    institute, employee, service, _, _ = setup(client)
    root, activated = prepare_sources(main_module.engine, institute, employee, service, monkeypatch)
    with Session(main_module.engine) as db:
        db.add(Appointment(id="waitlist-bad", institute_id=institute, employee_id=employee, service_id=service,
            customer_name="Malformed", start_time=NOW+timedelta(hours=5), end_time=NOW+timedelta(hours=4), status="confirmed"))
        db.commit()
        with pytest.raises(HTTPException): read(db, institute, root, activated)
        db.delete(db.get(Appointment, "waitlist-bad")); db.commit()
        cancelled = lifecycle.create(db, institute, transition(root, "cancel", activated, root, "cancel"), "signed")
        with pytest.raises(HTTPException): read(db, institute, root, activated)
        result = read(db, institute, root, cancelled)
        assert result.unavailable_reason == "cancelled" and result.review is None


def test_joint_resource_reservation_absence_and_overdue_customer_execution(client, monkeypatch):
    institute, employee, service, _, _ = setup(client)
    root, activated = prepare_sources(main_module.engine, institute, employee, service, monkeypatch)
    with Session(main_module.engine) as db:
        db.add(Employee(id="waitlist-other", institute_id=institute, first_name="Other", skills=[], status="unavailable"))
        db.flush()
        db.add(Appointment(id="resource-owner", institute_id=institute, employee_id="waitlist-other", service_id=service,
            customer_name="Other", start_time=NOW+timedelta(hours=1), end_time=NOW+timedelta(hours=1, minutes=30), status="confirmed"))
        db.flush()
        db.add(ResourceReservation(id="occupied-room", institute_id=institute, resource_id="waitlist-room", appointment_id="resource-owner",
            start_time=NOW+timedelta(hours=1), end_time=NOW+timedelta(hours=1, minutes=30), status="reserved"))
        db.commit()
        assert read(db, institute, root, activated).review.options[0].start == NOW+timedelta(hours=1, minutes=30)
        assert db.scalar(select(func.count()).select_from(ResourceReservation)) == 1
        db.delete(db.get(ResourceReservation, "occupied-room")); db.delete(db.get(Appointment, "resource-owner")); db.commit()
        db.add(EmployeeAbsence(id="waitlist-absence", institute_id=institute, employee_id=employee, kind="leave",
            start_time=NOW+timedelta(hours=1), end_time=NOW+timedelta(hours=1, minutes=30), reason="Declared leave",
            actor_id="signed", idempotency_key="waitlist-absence", created_at=NOW))
        db.commit()
        assert read(db, institute, root, activated).review.options[0].start == NOW+timedelta(hours=1, minutes=30)
        db.delete(db.get(EmployeeAbsence, "waitlist-absence")); db.commit()
        db.add(Appointment(id="overdue-care", institute_id=institute, employee_id=employee, service_id=service,
            customer_id="waitlist-customer", customer_name="Fixture", start_time=NOW-timedelta(hours=2),
            end_time=NOW-timedelta(hours=1), status="in_progress"))
        db.commit()
        result = read(db, institute, root, activated)
        assert result.review.unavailable_reason == "customer_capacity_unknown"
        assert result.evidence.employee_reasons[employee] == "overdue_active_booking"


def test_customer_session_source_and_missing_machine_configuration(client, monkeypatch):
    institute, employee, service, _, _ = setup(client)
    root, activated = prepare_sources(main_module.engine, institute, employee, service, monkeypatch)
    with Session(main_module.engine) as db:
        db.add(QueueTicket(id="current-care", institute_id=institute, customer_id="waitlist-customer", ticket_number="W", status="in_progress", arrival_time=NOW))
        db.flush()
        db.add(TicketLine(id="current-line", ticket_id="current-care", service_id=service, quantity=1, duration_minutes=90))
        db.flush()
        db.add(ServiceSession(id="current-session", institute_id=institute, employee_id=employee, service_id=service,
            ticket_line_id="current-line", start_time=NOW, planned_end_time=NOW+timedelta(hours=1, minutes=30), duration_minutes=90, status="in_progress"))
        db.commit()
        result = read(db, institute, root, activated)
        assert result.evidence.customer_session_ids == ("current-session",)
        assert result.review.options[0].start == NOW+timedelta(hours=1, minutes=30)
        db.get(ServiceSession, "current-session").planned_end_time = NOW-timedelta(minutes=1)
        db.get(ServiceSession, "current-session").start_time = NOW-timedelta(hours=1); db.commit()
        assert read(db, institute, root, activated).review.unavailable_reason == "customer_capacity_unknown"
        db.delete(db.get(ServiceSession, "current-session")); db.commit()
        db.get(Service, service).requires_machine = True
        db.delete(db.get(ResourceRequirement, "waitlist-need")); db.commit()
        assert read(db, institute, root, activated).review.unavailable_reason == "resource_configuration_unknown"
