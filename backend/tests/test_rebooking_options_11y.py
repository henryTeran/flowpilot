from datetime import date, timedelta
import pytest
from fastapi import HTTPException
from sqlalchemy import event
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.workforce import rebooking, rebooking_options
from app.modules.workforce.absence_schemas import AbsenceCancel
from app.modules.planning.models import ServiceSession
from app.modules.appointments.models import Appointment, BookingEvent
from test_rebooking_sources_11t import exercise as seed
from test_rebooking_11u import NOW, payload
from test_postgres_scheduling_4d import postgres_flow
from test_workforce_absences_11b import setup
from test_ticket_workflow import _auth_headers


def exercise(engine, institute, employee, service, monkeypatch):
    seed(engine, institute, employee, service)
    monkeypatch.setattr(rebooking, "utcnow", lambda: NOW)
    monkeypatch.setattr(rebooking_options, "utcnow", lambda: NOW)
    with Session(engine) as db:
        def read(offset=0, limit=20, day=date(2026, 10, 7)):
            return rebooking_options.read_sources(db, institute, employee, day, limit, offset)
        value = read()
        assert value.page.total == 2 and len(value.rows) == 2 and value.complete_sources is False
        assert value.basis == "actual_completion_day"
        assert {r.kind for r in value.rows} == {"session", "appointment"}
        assert all(r.exclusion is None and r.capture.customer_id == "rebook-customer" for r in value.rows)
        assert all(r.capture.employee_id == employee for r in value.rows)
        targets = rebooking_options.read_targets(db, institute, "session", "rebook-session")
        assert targets.page.total == 2
        target = next(r for r in targets.rows if r.id == "rebook-target")
        assert target.capture.creation_event_id == "rebook-event" and target.exclusion is None
        assert next(r for r in targets.rows if r.id == "rebook-original").exclusion == "invalid_booking"
        booking_event = db.get(BookingEvent, "rebook-event")
        db.add(BookingEvent(id="duplicate-created", institute_id=institute, appointment_id="rebook-target", event_type="created",
            occurred_at=booking_event.occurred_at, after=booking_event.after)); db.flush()
        ambiguous = next(r for r in rebooking_options.read_targets(db, institute, "session", "rebook-session").rows if r.id == "rebook-target")
        assert ambiguous.creation_events == 2 and ambiguous.exclusion == "invalid_booking" and ambiguous.capture is None
        db.delete(db.get(BookingEvent, "duplicate-created")); db.flush()
        original = rebooking.create(db, institute, payload(), "signed")
        linked_target = next(r for r in rebooking_options.read_targets(db, institute, "session", "rebook-session").rows if r.id == "rebook-target")
        assert linked_target.already_attributed and linked_target.exclusion == "already_attributed" and linked_target.capture is None
        value = read(); blocked = next(r for r in value.rows if r.kind == "session")
        assert blocked.already_attributed and blocked.exclusion == "already_attributed" and blocked.capture is None
        rebooking.cancel(db, institute, original.id, AbsenceCancel(reason="Correction", idempotency_key="options-cancel"), "signed")
        assert next(r for r in read().rows if r.kind == "session").exclusion is None
        assert next(r for r in rebooking_options.read_targets(db, institute, "session", "rebook-session").rows if r.id == "rebook-target").exclusion is None
        target_record = db.get(Appointment, "rebook-target")
        target_record.customer_id = None; db.flush()
        assert rebooking_options.read_targets(db, institute, "session", "rebook-session").page.total == 1
        target_record.customer_id = "rebook-customer"; db.flush()
        db.add(Appointment(id="unknown-start", institute_id=institute, employee_id=employee, service_id=service,
            customer_name="Owned fixture", customer_id="rebook-customer", start_time=NOW-timedelta(days=1), end_time=NOW,
            actual_start_time=None, actual_end_time=NOW-timedelta(minutes=5), status="completed"))
        for identifier, first, last in [("future", NOW+timedelta(microseconds=1), NOW+timedelta(microseconds=2)),
                ("unknown-customer", NOW-timedelta(minutes=20), NOW-timedelta(minutes=10)),
                ("boundary-start", NOW.replace(hour=22)-timedelta(days=1, minutes=10), NOW.replace(hour=22)-timedelta(days=1)),
                ("boundary-end", NOW.replace(hour=21), NOW.replace(hour=22))]:
            db.add(ServiceSession(id=identifier, institute_id=institute, employee_id=employee, service_id=service,
                start_time=first, real_end_time=last, planned_end_time=NOW+timedelta(days=9), duration_minutes=60, status="completed"))
        # Wholly unlocated completion never borrows its planned ending to enter a day.
        db.add(ServiceSession(id="unknown-ending", institute_id=institute, employee_id=employee, service_id=service,
            start_time=NOW-timedelta(minutes=10), real_end_time=None, planned_end_time=NOW, duration_minutes=10, status="completed"))
        db.commit()
        value = read(); assert value.page.total == 6
        rows = {r.id: r for r in value.rows}
        assert rows["unknown-start"].exclusion == "invalid_execution"
        assert rows["future"].exclusion == "future_end"
        assert rows["unknown-customer"].exclusion == "unknown_customer"
        assert "boundary-start" in rows and "boundary-end" not in rows and "unknown-ending" not in rows
        assert "customer_name" not in value.model_dump_json() and "phone" not in value.model_dump_json()
        for index in range(21):
            last = NOW-timedelta(minutes=30, microseconds=index)
            db.add(ServiceSession(id=f"paged-{index}", institute_id=institute, employee_id=employee, service_id=service,
                start_time=last-timedelta(minutes=1), real_end_time=last, planned_end_time=NOW, duration_minutes=1, status="completed"))
        db.commit()
        statements = []
        def observe(conn, cursor, statement, parameters, context, executemany):
            if statement.lstrip().upper().startswith("SELECT"): statements.append(statement)
        event.listen(engine, "before_cursor_execute", observe)
        try:
            for offset, size in [(0, 20), (20, 7)]:
                statements.clear(); value = read(offset)
                assert value.page.total == 27 and len(value.rows) == size and len(statements) <= 6
        finally: event.remove(engine, "before_cursor_execute", observe)
        assert read(day=date(2025, 10, 26)).end-read(day=date(2025, 10, 26)).start == timedelta(hours=25)
        from app.modules.workforce.rebooking_sources import booking
        source = rebooking_options.read_targets(db, institute, "session", "rebook-session").source
        with pytest.raises(HTTPException): booking(db, institute, "missing-target", source, NOW)
        for index in range(21):
            db.add(Appointment(id=f"target-page-{index}", institute_id=institute, employee_id=employee, service_id=service,
                customer_name="Private fixture", customer_id="rebook-customer", status="scheduled", start_time=NOW+timedelta(days=index+1),
                end_time=NOW+timedelta(days=index+1, minutes=10)))
        db.commit()
        event.listen(engine, "before_cursor_execute", observe)
        try:
            for offset, size in [(0, 20), (20, 4)]:
                statements.clear()
                targets = rebooking_options.read_targets(db, institute, "session", "rebook-session", offset=offset)
                assert targets.page.total == 24 and len(targets.rows) == size and len(statements) <= 8
                assert all(r.capture is None and r.creation_events == 0 for r in targets.rows if r.id.startswith("target-page-"))
        finally: event.remove(engine, "before_cursor_execute", observe)


def test_sqlite_source_choices_and_http_scope(client, monkeypatch):
    institute, employee, service, path, headers = setup(client)
    exercise(main_module.engine, institute, employee, service, monkeypatch)
    url = path+f"/employees/{employee}/rebooking-sources?day=2026-10-07"
    assert client.get(url, headers=headers).json()["page"]["total"] == 27
    assert client.get(url, headers=_auth_headers("accueil", institute)).status_code == 403
    assert client.get(url, headers=_auth_headers("responsable_institut", "foreign")).status_code == 403
    assert client.get(url+"&limit=51", headers=headers).status_code == 422
    assert client.get(url.replace("2026-10-07", "9999-12-31"), headers=headers).status_code == 400
    target_url = path+"/rebooking-targets/session/rebook-session"
    assert client.get(target_url, headers=headers).json()["source"]["customer_id"] == "rebook-customer"
    assert client.get(target_url, headers=_auth_headers("accueil", institute)).status_code == 403
    assert client.get(target_url, headers=_auth_headers("responsable_institut", "foreign")).status_code == 403
    assert client.get(target_url+"?limit=51", headers=headers).status_code == 422
    assert client.get(target_url.replace("/session/", "/invalid/"), headers=headers).status_code == 422


def test_actual_postgres_source_choices(postgres_flow, monkeypatch):
    exercise(*postgres_flow, monkeypatch)
