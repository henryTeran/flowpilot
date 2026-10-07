from datetime import date, timedelta
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Event
import pytest
from sqlalchemy import event
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.workforce import rebooking, rebooking_day
from app.modules.workforce.absence_schemas import AbsenceCancel
from app.modules.workforce.models import EmployeeRebooking
from app.modules.appointments.models import Appointment
from test_rebooking_sources_11t import exercise as seed
from test_rebooking_11u import NOW, payload
from test_postgres_scheduling_4d import postgres_flow
from test_workforce_absences_11b import setup
from test_ticket_workflow import _auth_headers


def exercise(engine, institute, employee, service, monkeypatch):
    seed(engine, institute, employee, service)
    monkeypatch.setattr(rebooking, "utcnow", lambda: NOW)
    monkeypatch.setattr(rebooking_day, "utcnow", lambda: NOW)
    with Session(engine) as db:
        original = rebooking.create(db, institute, payload(), "signed")
        def read(day=date(2026, 10, 7)):
            return rebooking_day.read(db, institute, employee, day)
        value = read()
        assert value.page.total == 1 and value.counts["booked_return"] == 1
        assert value.basis == "declaration_recorded_at" and value.conversion_basis_points is None and value.complete_attribution is False
        assert value.rows[0].original == original
        target = db.get(Appointment, "rebook-target")
        for status, state in [("cancelled", "cancelled_booking"), ("no_show", "no_show"), ("completed", "unknown_target"), ("arrived", "booked_return")]:
            target.status = status; db.commit()
            value = read(); assert value.rows[0].state == state and value.counts[state] == 1
            assert value.rows[0].original == original
        target.status = "completed"; target.actual_start_time = NOW-timedelta(minutes=20); target.actual_end_time = NOW-timedelta(minutes=10); db.commit()
        assert read().counts["completed_return"] == 1
        assert read().rows[0].actual_end == NOW-timedelta(minutes=10)
        for first, last in [(NOW-timedelta(hours=2), NOW-timedelta(minutes=10)), (NOW, NOW+timedelta(microseconds=1)), (NOW, NOW), (None, NOW)]:
            target.actual_start_time = first; target.actual_end_time = last; db.commit()
            assert read().counts["unknown_target"] == 1
        target.customer_id = None; target.status = "scheduled"; db.commit()
        assert read().counts["unknown_target"] == 1
        monkeypatch.setattr(rebooking_day, "utcnow", lambda: NOW-timedelta(microseconds=1))
        assert read().counts["future_recording"] == 1
        rebooking.cancel(db, institute, original.id, AbsenceCancel(reason="Correction", idempotency_key="day-cancel"), "signed")
        assert read().counts["cancelled_declaration"] == 1
        assert read(date(2026, 10, 8)).page.total == 0
        assert read(date(2025, 10, 26)).end-read(date(2025, 10, 26)).start == timedelta(hours=25)
        assert read(date(2025, 3, 30)).end-read(date(2025, 3, 30)).start == timedelta(hours=23)
        from app.modules.institutes.models import Institute
        institute_row = db.get(Institute, institute); old_zone = institute_row.timezone
        institute_row.timezone = "Pacific/Apia"; db.commit()
        skipped = read(date(2011, 12, 30))
        assert skipped.start == skipped.end and skipped.page.total == 0
        institute_row.timezone = old_zone; db.commit()
        # Owned historical corrections exercise aggregate/page separation.
        # They are cancelled facts, not concurrent active credits.
        for index in range(21):
            row = EmployeeRebooking(id=f"history-{index}", institute_id=institute, employee_id=employee,
                session_id=original.source_id, target_appointment_id=original.target_appointment_id,
                source_capture=original.source_capture.model_dump(mode="json"), booking_capture=original.booking_capture.model_dump(mode="json"),
                actor_id="signed", reason="Historical correction", idempotency_key=f"history-{index}", created_at=NOW)
            db.add(row); db.flush()
            from app.modules.workforce.models import RebookingCancellation
            db.add(RebookingCancellation(id=f"history-cancel-{index}", institute_id=institute, rebooking_id=row.id,
                actor_id="signed", reason="Historical correction", idempotency_key=f"history-cancel-{index}", created_at=NOW))
        db.commit()
        statements = []
        def observe(conn, cursor, statement, parameters, context, executemany):
            if statement.lstrip().upper().startswith("SELECT"): statements.append(statement)
        event.listen(engine, "before_cursor_execute", observe)
        try:
            for offset, length in [(0, 20), (20, 2)]:
                statements.clear()
                value = rebooking_day.read(db, institute, employee, date(2026, 10, 7), offset=offset)
                assert value.page.total == value.counts["cancelled_declaration"] == 22 and len(value.rows) == length
                assert len(statements) <= 6
        finally: event.remove(engine, "before_cursor_execute", observe)


def test_sqlite_rebooking_day_and_http_scope(client, monkeypatch):
    institute, employee, service, path, headers = setup(client)
    exercise(main_module.engine, institute, employee, service, monkeypatch)
    url = path+f"/employees/{employee}/rebooking-day?day=2026-10-07"
    assert client.get(url, headers=headers).json()["page"]["total"] == 22
    assert client.get(url, headers=_auth_headers("accueil", institute)).status_code == 403
    assert client.get(url, headers=_auth_headers("responsable_institut", "foreign")).status_code == 403
    assert client.get(url+"&limit=51", headers=headers).status_code == 422
    assert client.get(url.replace("2026-10-07", "9999-12-31"), headers=headers).status_code == 400


def test_actual_postgres_rebooking_day(postgres_flow, monkeypatch):
    exercise(*postgres_flow, monkeypatch)


def test_actual_postgres_day_read_blocks_writer_until_counts_and_page_are_captured(postgres_flow, monkeypatch):
    engine, institute, employee, service = postgres_flow
    seed(engine, institute, employee, service)
    monkeypatch.setattr(rebooking, "utcnow", lambda: NOW)
    monkeypatch.setattr(rebooking_day, "utcnow", lambda: NOW)
    paused, release, writer_started = Event(), Event(), Event()
    def observe(conn, cursor, statement, parameters, context, executemany):
        if paused.is_set() and "FROM institutes" in statement and "FOR UPDATE" in statement:
            writer_started.set()
        if statement.lstrip().startswith("SELECT employee_rebookings.created_at"):
            paused.set(); assert release.wait(10)
    def reader():
        with Session(engine) as db: return rebooking_day.read(db, institute, employee, date(2026, 10, 7))
    def writer():
        with Session(engine) as db:
            return rebooking.create(db, institute, payload("after-capture"), "signed")
    event.listen(engine, "before_cursor_execute", observe)
    try:
        with ThreadPoolExecutor(2) as pool:
            reading = pool.submit(reader)
            assert paused.wait(10)
            writing = pool.submit(writer)
            assert writer_started.wait(10)
            try:
                with pytest.raises(TimeoutError): writing.result(timeout=0.2)
            finally: release.set()
            captured = reading.result(timeout=10); writing.result(timeout=10)
            assert captured.page.total == 0 and captured.rows == [] and sum(captured.counts.values()) == 0
    finally:
        release.set(); event.remove(engine, "before_cursor_execute", observe)
    with Session(engine) as db:
        assert rebooking_day.read(db, institute, employee, date(2026, 10, 7)).counts["booked_return"] == 1
