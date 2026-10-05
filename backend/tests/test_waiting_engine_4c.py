from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

import app.main as main_module
from app.modules.appointments.models import Appointment
from app.modules.employees.models import Employee
from app.modules.planning.models import ServiceSession
from app.modules.scheduling.waiting_domain import EmployeeTimeline, QueueWork, next_fitting_start, project_queue
from app.modules.scheduling.waiting_service import waiting_projections
from app.modules.tickets.models import QueueTicket, TicketLine
from app.shared.time import utcnow
from test_ticket_workflow import _auth_headers, _bootstrap_reference_data, _create_ticket


NOW = datetime(2026, 10, 5, 10, tzinfo=timezone.utc)


def at(minutes):
    return NOW + timedelta(minutes=minutes)


@pytest.mark.parametrize("duration,bookings,expected", [
    (20, ((at(20), at(40)),), 0),  # touching boundary is allowed
    (21, ((at(20), at(40)),), 40),
    (45, ((at(20), at(40)), (at(60), at(80))), 80),
    (30, ((at(-10), at(10)), (at(5), at(20))), 20),
    (30, ((at(-40), at(-10)),), 0),
])
def test_full_duration_fits_appointment_windows(duration, bookings, expected):
    assert next_fitting_start(NOW, duration, bookings) == at(expected)


def test_fifo_parallel_workers_stable_ties_and_duration():
    employees = [EmployeeTimeline("b", NOW), EmployeeTimeline("a", NOW)]
    queue = [QueueWork("first", 45), QueueWork("second", 20), QueueWork("third", 30)]
    result = project_queue(employees, queue)
    assert result["first"].employee_id == "a"
    assert result["second"].employee_id == "b"
    assert result["third"].estimated_start_time == at(20)
    assert result == project_queue(list(reversed(employees)), queue)


def test_reservation_keeps_its_employee_and_capacity():
    result = project_queue([EmployeeTimeline("a", NOW)], [
        QueueWork("unassigned", 20), QueueWork("reserved", 45, "a"),
    ])
    assert result["reserved"].estimated_start_time == NOW
    assert result["unassigned"].estimated_start_time == at(45)
    assert result["reserved"].estimated_end_time == at(45)


def test_unknown_reserved_employee_does_not_move_to_another():
    result = project_queue([EmployeeTimeline("a", NOW)], [
        QueueWork("reserved", 45, "paused"), QueueWork("next", 20),
    ])
    assert result["reserved"].estimated_start_time is None
    assert result["reserved"].reason == "capacity_unknown"
    assert result["next"].estimated_start_time == NOW
    assert project_queue([], [QueueWork("none", 30)])["none"].estimated_start_time is None


@pytest.fixture
def setup_flow(client):
    institute, employees, services = _bootstrap_reference_data(client)
    headers = _auth_headers(institute_id=institute)
    with Session(main_module.engine) as db:
        for employee in employees:
            db.get(Employee, employee["id"]).status = "offline"
        db.get(Employee, employees[0]["id"]).status = "available"
        db.commit()
    return institute, employees, services, headers


def test_projection_uses_snapshots_quantity_appointments_and_tenant_scope(client, setup_flow):
    institute, employees, services, headers = setup_flow
    first = _create_ticket(client, institute, services[0]["id"])
    second = _create_ticket(client, institute, services[0]["id"])
    with Session(main_module.engine) as db:
        line = db.query(TicketLine).filter_by(ticket_id=first["id"]).one()
        line.duration_minutes, line.quantity = 15, 2
        db.query(TicketLine).filter_by(ticket_id=second["id"]).one().duration_minutes = 45
        db.get(QueueTicket, first["id"]).arrival_time = at(-2)
        db.get(QueueTicket, second["id"]).arrival_time = at(-1)
        db.add(Appointment(id="booked", institute_id=institute, employee_id=employees[0]["id"],
                           service_id=services[0]["id"], customer_name="Test",
                           start_time=at(40), end_time=at(60), status="scheduled"))
        db.add(Appointment(id="foreign", institute_id="other", employee_id=employees[0]["id"],
                           service_id=services[0]["id"], customer_name="Test",
                           start_time=at(0), end_time=at(120), status="scheduled"))
        db.commit()
        results = waiting_projections(db, institute, NOW)
        assert results[first["id"]].estimated_start_time == NOW
        assert results[second["id"]].estimated_start_time == at(60)


def test_live_queue_recalculates_after_extension_and_finish(client, setup_flow):
    institute, employees, services, headers = setup_flow
    first = _create_ticket(client, institute, services[0]["id"])
    second = _create_ticket(client, institute, services[0]["id"])
    started = client.post("/api/v1/planning/sessions/start", headers=headers, json={
        "ticket_id": first["id"], "employee_id": employees[0]["id"], "service_id": services[0]["id"],
    })
    assert started.status_code == 200, started.text
    session = started.json()
    path = f"/api/v1/tickets/waiting?institute_id={institute}"
    def estimate():
        response = client.get(path, headers=headers)
        assert response.status_code == 200
        return next(ticket for ticket in response.json() if ticket["id"] == second["id"])["estimated_start_time"]
    before = datetime.fromisoformat(estimate())
    extended = client.patch(f"/api/v1/planning/sessions/{session['id']}/extend", headers=headers, json={"minutes": 10})
    assert extended.status_code == 200
    assert datetime.fromisoformat(estimate()) == before + timedelta(minutes=10)
    dashboard = client.get(f"/api/v1/dashboard/institutes/{institute}/live", headers=headers)
    assert dashboard.status_code == 200
    assert dashboard.json()["average_wait_minutes"] >= session["duration_minutes"] + 9
    assert client.patch(f"/api/v1/planning/sessions/{session['id']}/finish", headers=headers).status_code == 200
    assert datetime.fromisoformat(estimate()) < before


def test_overdue_and_paused_capacity_are_unknown(client, setup_flow):
    institute, employees, services, headers = setup_flow
    ticket = _create_ticket(client, institute, services[0]["id"])
    now = utcnow()
    with Session(main_module.engine) as db:
        db.add(ServiceSession(id="overdue", institute_id=institute, employee_id=employees[0]["id"],
                              service_id=services[0]["id"], start_time=now - timedelta(minutes=40),
                              planned_end_time=now - timedelta(minutes=10), duration_minutes=30, status="in_progress"))
        db.commit()
        assert waiting_projections(db, institute, now)[ticket["id"]].estimated_start_time is None
        db.delete(db.get(ServiceSession, "overdue"))
        db.get(Employee, employees[0]["id"]).status = "pause"
        db.commit()
        assert waiting_projections(db, institute, now)[ticket["id"]].estimated_start_time is None
    response = client.get(f"/api/v1/tickets/waiting?institute_id={institute}", headers=headers)
    assert response.json()[0]["estimated_start_time"] is None
    dashboard = client.get(f"/api/v1/dashboard/institutes/{institute}/live", headers=headers)
    assert dashboard.json()["average_wait_minutes"] is None
