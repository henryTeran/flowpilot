from datetime import date, datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import event
import app.main as main_module
from app.modules.workforce import occupation, work_intervals
from app.modules.workforce.work_interval_schemas import WorkIntervalCreate
from app.modules.planning.models import ServiceSession
from app.modules.appointments.models import Appointment
from test_workforce_absences_11b import setup
from test_postgres_scheduling_4d import postgres_flow
from test_ticket_workflow import _auth_headers


def exercise(engine, institute, employee, service):
    first = datetime(2025, 10, 26, 3, tzinfo=timezone.utc)
    with Session(engine) as db:
        work_intervals.create(db, institute, WorkIntervalCreate(employee_id=employee, start_time=first,
            end_time=first+timedelta(hours=2), reason="Declared", idempotency_key="occupation-work"), "signed")
        db.add(ServiceSession(id="known", institute_id=institute, employee_id=employee, service_id=service,
            start_time=first-timedelta(hours=1), planned_end_time=first+timedelta(hours=10), real_end_time=first+timedelta(hours=1), duration_minutes=600, status="completed"))
        db.add(Appointment(id="known-appointment", institute_id=institute, employee_id=employee, service_id=service, customer_name="Owned fixture",
            start_time=first, end_time=first+timedelta(hours=10), actual_start_time=first+timedelta(minutes=30), actual_end_time=first+timedelta(hours=1, microseconds=1), status="completed"))
        db.add(ServiceSession(id="planned", institute_id=institute, employee_id=employee, service_id=service,
            start_time=first, planned_end_time=first+timedelta(hours=10), real_end_time=None, duration_minutes=600, status="planned"))
        db.commit()
        read = occupation.EmployeeOccupation.model_validate(occupation.read(db, institute, employee, date(2025, 10, 26), limit=1))
        assert read.page.total == 2 and len(read.rows) == 1 and read.diagnostics["retained"] == 2
        assert read.known_busy_duration_us == "7200000001"
        assert read.covered_busy_duration_us == "3600000001" and read.outside_recorded_work_duration_us == "3600000000"
        assert read.recorded_occupation_basis_points == "5000" and read.complete_activity is False
        db.add(ServiceSession(id="unknown", institute_id=institute, employee_id=employee, service_id=service,
            start_time=first-timedelta(days=1), planned_end_time=first-timedelta(hours=23), real_end_time=None, duration_minutes=60, status="in_progress"))
        db.add(Appointment(id="unknown-start", institute_id=institute, employee_id=employee, service_id=service, customer_name="Owned fixture",
            start_time=first-timedelta(days=1), end_time=first-timedelta(hours=23), actual_start_time=None, actual_end_time=first, status="completed"))
        db.commit()
        read = occupation.EmployeeOccupation.model_validate(occupation.read(db, institute, employee, date(2025, 10, 26)))
        assert read.diagnostics["missing_end"] == read.diagnostics["missing_start"] == 1
        assert read.recorded_occupation_basis_points is None and read.covered_busy_duration_us == "3600000001"
        unknown = next(r for r in read.rows if r.id == "unknown")
        assert unknown.actual_end is None and unknown.duration_us is None
        for identifier, last, status in [("invalid", first-timedelta(seconds=1), "completed"),
                                         ("future", datetime(9998, 1, 1, tzinfo=timezone.utc), "completed"),
                                         ("unfinalized", first+timedelta(minutes=30), "in_progress")]:
            db.add(ServiceSession(id=identifier, institute_id=institute, employee_id=employee, service_id=service,
                start_time=first, planned_end_time=first+timedelta(hours=10), real_end_time=last, duration_minutes=600, status=status))
        db.commit()
        read = occupation.EmployeeOccupation.model_validate(occupation.read(db, institute, employee, date(2025, 10, 26)))
        assert all(read.diagnostics[key] == 1 for key in ("invalid_interval", "future_end", "unfinalized"))
        assert read.recorded_occupation_basis_points is None and read.covered_busy_duration_us == "3600000001"
        empty = occupation.EmployeeOccupation.model_validate(occupation.read(db, institute, employee, date(2020, 1, 1)))
        assert empty.page.total == 0 and empty.recorded_occupation_basis_points is None


def test_sqlite_recorded_occupation_and_role_scope(client):
    institute, employee, service, _, _ = setup(client)
    exercise(main_module.engine, institute, employee, service)
    path = f"/api/v1/workforce/institutes/{institute}/employees/{employee}/occupation?day=2025-10-26"
    assert client.get(path, headers=_auth_headers("responsable_institut", institute)).status_code == 200
    assert client.get(path, headers=_auth_headers("accueil", institute)).status_code == 403
    assert client.get(path, headers=_auth_headers("responsable_institut", "foreign")).status_code == 403
    assert client.get(path+"&limit=51", headers=_auth_headers("responsable_institut", institute)).status_code == 422


def test_actual_postgres_recorded_occupation(postgres_flow):
    engine, institute, employee, service = postgres_flow
    exercise(engine, institute, employee, service)


def test_occupation_totals_cover_all_pages_with_constant_query_count(client):
    institute, employee, service, _, _ = setup(client)
    first = datetime(2025, 10, 26, 3, tzinfo=timezone.utc)
    with Session(main_module.engine) as db:
        work_intervals.create(db, institute, WorkIntervalCreate(employee_id=employee, start_time=first,
            end_time=first+timedelta(hours=2), reason="Declared", idempotency_key="paged-work"), "signed")
        for index in range(21):
            start = first+timedelta(minutes=index)
            db.add(ServiceSession(id=f"paged-{index}", institute_id=institute, employee_id=employee, service_id=service,
                start_time=start, planned_end_time=start+timedelta(hours=10), real_end_time=start+timedelta(microseconds=1), duration_minutes=600, status="completed"))
        db.commit()
    statements = []
    def observe(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"): statements.append(statement)
    event.listen(main_module.engine, "before_cursor_execute", observe)
    try:
        for offset, length in [(0, 20), (20, 1)]:
            statements.clear()
            with Session(main_module.engine) as db:
                read = occupation.EmployeeOccupation.model_validate(occupation.read(db, institute, employee, date(2025, 10, 26), offset=offset))
            assert read.page.total == 21 and len(read.rows) == length and read.diagnostics["retained"] == 21
            assert read.covered_busy_duration_us == read.known_busy_duration_us == "21"
            assert len(statements) <= 14
    finally:
        event.remove(main_module.engine, "before_cursor_execute", observe)
