from datetime import date, datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from sqlalchemy import event
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.institutes.models import Institute
from app.modules.workforce import work_intervals, work_hours
from app.modules.workforce.work_interval_schemas import WorkIntervalCreate
from app.modules.workforce.absence_schemas import AbsenceCancel
from app.modules.workforce.models import EmployeeWorkInterval
from test_workforce_absences_11b import setup
from test_ticket_workflow import _auth_headers
from test_postgres_scheduling_4d import postgres_flow


def create(db, institute, employee, first, last, key):
    return work_intervals.create(db, institute, WorkIntervalCreate(employee_id=employee, start_time=first, end_time=last,
        reason="Declared effective work", idempotency_key=key), "signed")


def exercise(engine, institute, employee, monkeypatch):
    with Session(engine) as db:
        db.get(Institute, institute).timezone = "Europe/Zurich"; db.commit()
        # A tiny midnight-crossing declaration retains one microsecond in the day.
        start = datetime(2025, 10, 24, 22, tzinfo=timezone.utc)
        tiny = create(db, institute, employee, start-timedelta(microseconds=1), start+timedelta(microseconds=1), "tiny")
        read = work_hours.EmployeeWorkHours.model_validate(work_hours.read(db, institute, employee, date(2025, 10, 25)))
        assert read.known_union_duration_us == "1" and read.rows[0].duration_us == "1"
        assert read.complete_attendance is False and read.recorded_duration_us == "1"
        work_intervals.cancel(db, institute, tiny.id, AbsenceCancel(reason="Revised", idempotency_key="cancel-tiny"), "signed")
        cancelled = work_hours.EmployeeWorkHours.model_validate(work_hours.read(db, institute, employee, date(2025, 10, 25)))
        assert cancelled.page.total == 1 and cancelled.active_sources == 0
        assert cancelled.recorded_duration_us is None and cancelled.known_union_duration_us == "0"
        assert cancelled.rows[0].exclusion == "cancelled" and cancelled.rows[0].duration_us == "1"
        for day, first, last, hours in [
            (date(2025, 3, 30), datetime(2025, 3, 29, 23, tzinfo=timezone.utc), datetime(2025, 3, 30, 22, tzinfo=timezone.utc), 23),
            (date(2025, 10, 26), datetime(2025, 10, 25, 22, tzinfo=timezone.utc), datetime(2025, 10, 26, 23, tzinfo=timezone.utc), 25)]:
            record = create(db, institute, employee, first-timedelta(minutes=10), last+timedelta(minutes=10), str(day))
            for suffix, outside_start, outside_end in [("before", first-timedelta(hours=1), first), ("after", last, last+timedelta(hours=1))]:
                db.add(EmployeeWorkInterval(id=f"boundary-{day}-{suffix}", institute_id=institute, employee_id=employee,
                    start_time=outside_start, end_time=outside_end, actor_id="signed", reason="Owned boundary fixture",
                    idempotency_key=f"boundary-{day}-{suffix}", created_at=datetime(2026, 1, 1, tzinfo=timezone.utc)))
            db.commit()
            read = work_hours.EmployeeWorkHours.model_validate(work_hours.read(db, institute, employee, day))
            assert read.page.total == read.active_sources == 1
            assert read.recorded_duration_us == str(hours*3600000000)
            assert read.rows[0].clipped_start == first and read.rows[0].clipped_end == last
            assert read.rows[0].interval.id == record.id
        # Simulated legacy overlap bypasses supported writes: never double count it.
        db.add(EmployeeWorkInterval(id="legacy-overlap", institute_id=institute, employee_id=employee,
            start_time=datetime(2025, 10, 26, 0, tzinfo=timezone.utc), end_time=datetime(2025, 10, 26, 1, tzinfo=timezone.utc),
            actor_id="signed", reason="Legacy fixture", idempotency_key="legacy", created_at=datetime(2026, 1, 1, tzinfo=timezone.utc)))
        db.commit()
        read = work_hours.EmployeeWorkHours.model_validate(work_hours.read(db, institute, employee, date(2025, 10, 26), 1, 1))
        assert read.page.total == 2 and len(read.rows) == 1
        assert read.active_sources == 2 and read.overlap_sources == 1
        assert read.known_declared_duration_us == str(26*3600000000) and read.known_union_duration_us == str(25*3600000000)
        monkeypatch.setattr(work_hours, "utcnow", lambda: datetime(2020, 1, 1, tzinfo=timezone.utc))
        future = work_hours.EmployeeWorkHours.model_validate(work_hours.read(db, institute, employee, date(2025, 10, 26)))
        assert future.future_end_sources == 2 and future.recorded_duration_us is None and future.known_union_duration_us == "0"
        assert all(row.exclusion == "future_end" for row in future.rows)
        db.get(Institute, institute).timezone = "Pacific/Apia"; db.commit()
        skipped = work_hours.EmployeeWorkHours.model_validate(work_hours.read(db, institute, employee, date(2011, 12, 30)))
        assert skipped.start == skipped.end and skipped.page.total == 0 and skipped.recorded_duration_us is None


def test_sqlite_exact_work_hour_days_and_http_scope(client, monkeypatch):
    institute, employee, _, _, _ = setup(client)
    exercise(main_module.engine, institute, employee, monkeypatch)
    headers = _auth_headers("responsable_institut", institute)
    path = f"/api/v1/workforce/institutes/{institute}/employees/{employee}/work-hours"
    assert client.get(path+"?day=2011-12-30", headers=headers).status_code == 200
    assert client.get(path+"?day=9999-12-31", headers=headers).status_code == 400
    assert client.get(path+"?day=2025-10-26&limit=51", headers=headers).status_code == 422
    assert client.get(path+"?day=2025-10-26", headers=_auth_headers("accueil", institute)).status_code == 403
    assert client.get(path+"?day=2025-10-26", headers=_auth_headers("responsable_institut", "foreign")).status_code == 403
    assert client.get(path.replace(employee, "foreign")+"?day=2025-10-26", headers=headers).status_code == 404


def test_actual_postgres_exact_hour_days(postgres_flow, monkeypatch):
    engine, institute, employee, _ = postgres_flow
    exercise(engine, institute, employee, monkeypatch)


def test_work_hour_aggregate_covers_all_pages_without_per_source_queries(client):
    institute, employee, _, _, _ = setup(client)
    start = datetime(2025, 10, 26, 3, tzinfo=timezone.utc)
    with Session(main_module.engine) as db:
        for index in range(21):
            first = start+timedelta(minutes=index)
            create(db, institute, employee, first, first+timedelta(microseconds=1), f"page-{index}")
    statements = []
    def observe(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)
    event.listen(main_module.engine, "before_cursor_execute", observe)
    try:
        for offset, length in [(0, 20), (20, 1)]:
            statements.clear()
            with Session(main_module.engine) as db:
                read = work_hours.EmployeeWorkHours.model_validate(work_hours.read(db, institute, employee, date(2025, 10, 26), offset=offset))
            assert read.page.total == 21 and len(read.rows) == length
            assert read.recorded_duration_us == "21" and read.active_sources == 21
            assert len(statements) <= 8
    finally:
        event.remove(main_module.engine, "before_cursor_execute", observe)


def test_actual_postgres_hour_count_aggregate_and_page_hold_one_institute_lock(postgres_flow, monkeypatch):
    engine, institute, employee, _ = postgres_flow
    entered, completed, intercepted = Event(), Event(), Event()
    original_lock = work_intervals.lock_institute
    def writer_lock(db, identifier):
        entered.set()
        return original_lock(db, identifier)
    monkeypatch.setattr(work_intervals, "lock_institute", writer_lock)
    def writer():
        with Session(engine) as db:
            create(db, institute, employee, datetime(2025, 10, 26, 3, tzinfo=timezone.utc), datetime(2025, 10, 26, 4, tzinfo=timezone.utc), "locked")
        completed.set()
    with ThreadPoolExecutor(max_workers=1) as pool:
        futures = []
        def observe(connection, cursor, statement, parameters, context, executemany):
            if not intercepted.is_set() and "count(" in statement.lower() and "employee_work_intervals" in statement:
                intercepted.set(); futures.append(pool.submit(writer))
                assert entered.wait(timeout=5)
                assert not completed.wait(timeout=0.2)
        event.listen(engine, "before_cursor_execute", observe)
        try:
            with Session(engine) as db:
                read = work_hours.EmployeeWorkHours.model_validate(work_hours.read(db, institute, employee, date(2025, 10, 26)))
                assert intercepted.is_set() and read.page.total == read.active_sources == 0 and read.rows == []
                assert read.recorded_duration_us is None and not completed.is_set()
            futures[0].result(timeout=10)
            with Session(engine) as db:
                read = work_hours.EmployeeWorkHours.model_validate(work_hours.read(db, institute, employee, date(2025, 10, 26)))
                assert read.page.total == read.active_sources == len(read.rows) == 1
                assert read.recorded_duration_us == "3600000000"
        finally:
            event.remove(engine, "before_cursor_execute", observe)
