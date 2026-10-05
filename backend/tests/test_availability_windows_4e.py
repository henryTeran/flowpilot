from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database.base import Base
from app.modules.appointments.models import Appointment
from app.modules.employees.models import Employee
from app.modules.planning.models import ServiceSession
from app.modules.planning.service import get_institute_availability
from app.modules.scheduling.availability_domain import free_windows
from app.modules.scheduling.service import availability_engine, earliest_available_employee, next_available_time_for_employee
from app.modules.scheduling.service_4b import assignment_options_for_ticket
from app.modules.tickets.models import QueueTicket, TicketLine


NOW = datetime(2026, 10, 5, 10, tzinfo=timezone.utc)


def at(minutes):
    return NOW + timedelta(minutes=minutes)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Employee(id="emp", institute_id="inst", first_name="Test", status="available"))
        session.commit()
        yield session
    engine.dispose()


def appointment(db, name, start, end, tenant="inst", status="scheduled"):
    db.add(Appointment(id=name, institute_id=tenant, employee_id="emp", service_id="svc",
                       customer_name="Test", start_time=at(start), end_time=at(end), status=status))
    db.commit()


def active(db, name="session", end=20):
    db.add(ServiceSession(id=name, institute_id="inst", employee_id="emp", service_id="svc",
                          start_time=at(-20), planned_end_time=at(end), duration_minutes=40, status="in_progress"))
    db.commit()


@pytest.mark.parametrize("status", ["pause", "absent", "offline", "busy"])
def test_unknown_status_never_returns_now(db, status):
    db.get(Employee, "emp").status = status
    db.commit()
    result = availability_engine(db, "inst", "emp", now=NOW)
    assert not result.available
    assert result.current_slot.available_from is None
    assert result.to_dict()["current_slot"]["available_from"] is None
    assert next_available_time_for_employee(db, "inst", "emp", now=NOW) is None
    assert earliest_available_employee(db, "inst", now=NOW) is None


def test_busy_employee_without_known_work_is_not_assignable(db):
    db.get(Employee, "emp").status = "busy"
    db.add(QueueTicket(id="ticket", institute_id="inst", ticket_number="T-001", status="waiting", arrival_time=NOW))
    db.flush()
    db.add(TicketLine(id="line", ticket_id="ticket", service_id="svc", duration_minutes=30, quantity=1))
    db.commit()
    options = assignment_options_for_ticket(db, "inst", "ticket", NOW)
    assert not options[0].assignable
    assert options[0].available_from is None
    assert options[0].to_dict()["available_from"] is None


def test_overdue_session_is_unknown_even_with_another_known_session(db):
    active(db, "overdue", -1)
    active(db, "later", 30)
    assert next_available_time_for_employee(db, "inst", "emp", now=NOW) is None
    assert availability_engine(db, "inst", "emp", now=NOW).current_slot.blocking_session_id == "overdue"


def test_session_followed_by_chained_appointments_has_no_false_gap(db):
    active(db)
    appointment(db, "first", 15, 35)
    appointment(db, "second", 35, 50)
    appointment(db, "third", 45, 60)
    appointment(db, "fourth", 80, 100)
    result = availability_engine(db, "inst", "emp", now=NOW)
    assert not result.available
    assert result.current_slot.available_from == at(60)
    assert result.current_slot.available_until == at(80)
    assert result.upcoming_slots[0].available_from == at(100)
    assert earliest_available_employee(db, "inst", now=NOW) == ("emp", at(60))


def test_all_future_appointments_and_foreign_cancelled_exclusion(db):
    for i in range(8):
        appointment(db, f"booked-{i}", 10 + i * 20, 20 + i * 20)
    appointment(db, "foreign", 0, 300, tenant="other")
    appointment(db, "cancelled", 0, 300, status="cancelled")
    result = availability_engine(db, "inst", "emp", now=NOW)
    assert result.available
    assert result.current_slot.available_until == at(10)
    assert len(result.upcoming_slots) == 8
    assert result.upcoming_slots[-1].available_from == at(160)


def test_planning_uses_chained_availability_and_historical_overdue(db, monkeypatch):
    monkeypatch.setattr("app.modules.planning.service.utcnow", lambda: NOW)
    active(db)
    appointment(db, "first", 20, 40)
    planning = get_institute_availability(db, "inst")
    assert planning.employees[0].available_at == at(40)
    assert planning.wait_minutes == 40
    active(db, "yesterday", -1440)
    planning = get_institute_availability(db, "inst")
    assert planning.employees[0].employee_status == "delayed"
    assert planning.employees[0].available_at is None
    assert planning.employees[0].active_session_id == "yesterday"
    assert planning.next_available_at is None


def test_free_windows_merge_nested_and_adjacent_intervals():
    windows = free_windows(NOW, [(at(10), at(50), "outer"), (at(20), at(30), "inner"),
                                  (at(50), at(60), "adjacent")])
    assert windows == [(NOW, at(10), None), (at(60), None, "outer")]
