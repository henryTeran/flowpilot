from datetime import date, datetime, timedelta, timezone
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.revenue import capacity
from app.modules.employees.models import Employee
from app.modules.institutes.models import Institute
from app.modules.workforce.models import EmployeeWorkInterval
from app.modules.workforce import work_hours
from app.modules.planning.models import ServiceSession
from test_workforce_absences_11b import setup
from test_ticket_workflow import _auth_headers
from test_postgres_scheduling_4d import postgres_flow


NOW = datetime(2026, 1, 2, tzinfo=timezone.utc)
DAY = date(2025, 10, 26)
FIRST = datetime(2025, 10, 26, 3, tzinfo=timezone.utc)


def exercise(engine, institute, service, monkeypatch):
    monkeypatch.setattr(capacity, "utcnow", lambda: NOW)
    # If the trusted pin is accidentally discarded, future-end diagnostics will
    # change. Assert the entire aggregate and returned evidence share NOW.
    monkeypatch.setattr(work_hours, "utcnow", lambda: FIRST)
    with Session(engine) as db:
        for n in range(25):
            db.add(Employee(id=f"capacity-employee-{n:02}", institute_id=institute, first_name="Fixture", status="unavailable", skills=[]))
        db.flush()
        owned = db.scalars(select(Employee.id).where(Employee.institute_id == institute).order_by(Employee.id)).all()
        for n, employee in enumerate(owned):
            db.add(EmployeeWorkInterval(id=f"capacity-work-{n}", institute_id=institute, employee_id=employee,
                start_time=FIRST, end_time=FIRST+timedelta(hours=2), reason="Declared fixture", actor_id="manager",
                idempotency_key=f"capacity-{n}", created_at=NOW-timedelta(days=1)))
            db.add(ServiceSession(id=f"capacity-session-{n}", institute_id=institute, employee_id=employee, service_id=service,
                start_time=FIRST, planned_end_time=FIRST+timedelta(hours=1), real_end_time=FIRST+timedelta(hours=1),
                duration_minutes=60, status="completed"))
        db.commit()
        first = capacity.read(db, institute, DAY)
        last = capacity.read(db, institute, DAY, 20)
        assert len(first.rows) == 20 and len(last.rows) == len(owned)-20
        assert first.page.total == first.employee_count == len(owned)
        assert first.known_declared_union_duration_us == str(len(owned)*7200000000)
        assert first.known_covered_busy_duration_us == first.recorded_unoccupied_duration_us == str(len(owned)*3600000000)
        assert first.recorded_utilization_ratio == last.recorded_utilization_ratio
        assert first.window.captured_at == NOW and all(row.evidence.work_hours.generated_at == NOW for row in first.rows+last.rows)
        assert first.window.end-first.window.start == timedelta(hours=25)  # institute Europe/Zurich DST day
        assert first.bookable_capacity is None and first.physical_unused_capacity is None and first.estimated_value is None
        db.add(ServiceSession(id="capacity-uncertain", institute_id=institute, employee_id=owned[-1], service_id=service,
            start_time=FIRST, planned_end_time=FIRST+timedelta(hours=1), duration_minutes=60, real_end_time=None, status="in_progress"))
        db.commit()
        changed = capacity.read(db, institute, DAY, limit=1)
        assert changed.employees_with_uncertain_activity == 1
        assert changed.recorded_unoccupied_duration_us is None and changed.recorded_utilization_ratio is None
        assert changed.known_covered_busy_duration_us == first.known_covered_busy_duration_us
        assert capacity.read(db, institute, DAY, len(owned)).rows == ()
        no_hours = capacity.read(db, institute, date(2020, 1, 1))
        assert no_hours.employees_without_usable_hours == len(owned) and no_hours.recorded_unoccupied_duration_us is None
        for day in (date(2027, 1, 1), date(9999, 12, 31)):
            with pytest.raises(HTTPException): capacity.read(db, institute, day)
        for offset, limit in ((-1,20), (0,51), (True,20)):
            with pytest.raises(HTTPException): capacity.read(db, institute, DAY, offset, limit)
        for name in ("complete_attendance", "complete_activity"):
            with pytest.raises(ValueError): capacity.Capacity.model_validate({**first.model_dump(), name: 0})
        institute_row = db.get(Institute, institute)
        institute_row.timezone = "Pacific/Apia"; db.commit()
        with pytest.raises(HTTPException): capacity.read(db, institute, date(2011, 12, 30))
        institute_row.timezone = "Invalid/Zone"; db.commit()
        with pytest.raises(HTTPException): capacity.read(db, institute, DAY)
        institute_row.timezone = first.timezone; db.commit()
        return first


def test_sqlite_capacity_full_cohort_capture_and_signed_api(client, monkeypatch):
    institute, _, service, _, _ = setup(client)
    exercise(main_module.engine, institute, service, monkeypatch)
    path = f"/api/v1/revenue/institutes/{institute}/capacity?day=2025-10-26"
    headers = _auth_headers("responsable_institut", institute)
    assert client.get(path, headers=headers).status_code == 200
    for role, owner in (("accueil", institute), ("collaboratrice", institute), ("responsable_institut", "foreign")):
        assert client.get(path, headers=_auth_headers(role, owner)).status_code == 403
    assert client.get(path).status_code == 403
    assert client.get(path+"&limit=51", headers=headers).status_code == 422
    assert client.post(path, headers=headers).status_code == 405


def test_postgres_capacity_full_cohort_capture(postgres_flow, monkeypatch):
    engine, institute, _, service = postgres_flow
    exercise(engine, institute, service, monkeypatch)
