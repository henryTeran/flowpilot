from datetime import date, timedelta
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Event
import pytest
from sqlalchemy import event
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.appointments.models import Appointment
from app.modules.planning.models import ServiceSession
from app.modules.institutes.models import Institute
from app.modules.workforce.calendar import read_employee_day
from app.modules.workforce.calendar_schemas import EmployeeDayRead
from app.modules.workforce.models import EmployeeAbsence, AbsenceCancellation
from app.modules.workforce import absences
from app.modules.workforce.absence_schemas import AbsenceCreate
from app.modules.institutes.calendar import day_bounds
from app.shared.time import utcnow
from test_workforce_absences_11b import setup
from test_ticket_workflow import _auth_headers
from test_postgres_scheduling_4d import postgres_flow


def populate(db, institute, employee, service, day):
    db.get(Institute, institute).timezone = "Europe/Zurich"
    db.flush()
    start, end = day_bounds(db, institute, day)
    db.add(Appointment(id="overnight", institute_id=institute, employee_id=employee, service_id=service,
        customer_name="Owned calendar fixture", start_time=start-timedelta(minutes=30), end_time=start+timedelta(minutes=30),
        booked_start_time=start-timedelta(minutes=30), booked_end_time=start+timedelta(minutes=30),
        actual_start_time=start+timedelta(minutes=10), actual_end_time=start+timedelta(minutes=40), status="completed"))
    db.add(Appointment(id="edge-excluded", institute_id=institute, employee_id=employee, service_id=service,
        customer_name="Owned edge", start_time=end, end_time=end+timedelta(minutes=10), status="scheduled"))
    db.add(ServiceSession(id="unknown-end", institute_id=institute, employee_id=employee, service_id=service,
        start_time=start-timedelta(days=1), planned_end_time=start-timedelta(hours=23), duration_minutes=60, status="in_progress"))
    db.add(EmployeeAbsence(id="leave", institute_id=institute, employee_id=employee, kind="leave",
        start_time=start+timedelta(hours=2), end_time=start+timedelta(hours=3), reason="Original reason",
        idempotency_key="leave", actor_id="signed", created_at=utcnow()))
    db.flush()
    db.add(AbsenceCancellation(id="cancel", institute_id=institute, absence_id="leave", reason="Return",
        idempotency_key="cancel", actor_id="signed", created_at=utcnow()))
    db.commit()
    return start, end


@pytest.mark.parametrize("day,hours", [(date(2026, 3, 29), 23), (date(2026, 10, 25), 25)])
def test_http_employee_calendar_scopes_paginates_and_retains_planned_actual_and_cancelled_facts(client, day, hours):
    institute, employee, service, _, headers = setup(client)
    with Session(main_module.engine) as db:
        start, end = populate(db, institute, employee, service, day)
    path = f"/api/v1/workforce/institutes/{institute}/employees/{employee}/day?day={day}"
    reply = client.get(path + "&limit=2", headers=headers)
    assert reply.status_code == 200, reply.text
    result = EmployeeDayRead.model_validate(reply.json())
    assert result.day_end-result.day_start == timedelta(hours=hours)
    assert result.employee.id == employee and result.timezone == "Europe/Zurich"
    assert result.event_page.total == 3 and len(result.events) == 2
    assert result.events[0].id == "unknown-end" and result.events[0].actual_end_time is None
    appointment = result.events[1]
    assert appointment.id == "overnight" and appointment.start_time == start-timedelta(minutes=30)
    assert appointment.actual_start_time == start+timedelta(minutes=10)
    later = client.get(path + "&limit=2&offset=2", headers=headers).json()
    assert later["events"][0]["status"] == "cancelled" and later["events"][0]["cancellation_id"] == "cancel"
    assert later["events"][0]["reason"] == "Original reason"
    assert later["generated_at"] != later["day_start"]  # Availability is current, not a day prediction.
    assert client.get(path, headers=_auth_headers("accueil", institute)).status_code == 403
    assert client.get(path.replace(employee, "foreign"), headers=headers).status_code == 404
    assert client.get(path.replace(institute, "foreign"), headers=headers).status_code == 403
    assert client.get(path + "&limit=101", headers=headers).status_code == 422
    assert client.get(path.replace(str(day), "9999-12-31"), headers=headers).status_code == 400


def test_actual_postgres_calendar_union_retains_time_types_and_exact_source_identity(postgres_flow):
    engine, institute, employee, service = postgres_flow
    day = date(2026, 3, 29)
    with Session(engine) as db:
        start, end = populate(db, institute, employee, service, day)
        result = EmployeeDayRead.model_validate(read_employee_day(db, institute, employee, day))
        assert result.day_start == start and result.day_end == end
        assert [(row.source_kind, row.id) for row in result.events] == [
            ("session", "unknown-end"), ("appointment", "overnight"), ("absence", "leave")]
        assert result.events[-1].status == "cancelled" and result.events[-1].absence_kind == "leave"


def test_skipped_institute_day_is_empty_even_when_an_execution_is_open(client):
    institute, employee, service, _, headers = setup(client)
    day = date(2011, 12, 30)
    with Session(main_module.engine) as db:
        populate(db, institute, employee, service, day)
        db.get(Institute, institute).timezone = "Pacific/Apia"
        db.commit()
    reply = client.get(f"/api/v1/workforce/institutes/{institute}/employees/{employee}/day?day={day}", headers=headers)
    assert reply.status_code == 200, reply.text
    result = EmployeeDayRead.model_validate(reply.json())
    assert result.day_start == result.day_end and result.event_page.total == 0 and result.events == []


def test_actual_postgres_calendar_count_and_page_share_one_locked_original_view(postgres_flow):
    engine, institute, employee, _ = postgres_flow
    day = (utcnow()+timedelta(days=2)).date()
    counted, release, writing = Event(), Event(), Event()
    def pause_after_count(connection, cursor, statement, parameters, context, executemany):
        if "count(*)" in statement.lower() and "employee_calendar_events" in statement:
            counted.set()
            assert release.wait(timeout=10)
    def read():
        with Session(engine) as db:
            return EmployeeDayRead.model_validate(read_employee_day(db, institute, employee, day))
    def write():
        writing.set()
        with Session(engine) as db:
            start, _ = day_bounds(db, institute, day)
            return absences.create(db, institute, AbsenceCreate(employee_id=employee, kind="leave",
                start_time=start+timedelta(hours=12), end_time=start+timedelta(hours=13),
                reason="Concurrent original", idempotency_key="concurrent-original"), "signed")
    event.listen(engine, "after_cursor_execute", pause_after_count)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            original = pool.submit(read)
            try:
                assert counted.wait(timeout=10)
                mutation = pool.submit(write)
                assert writing.wait(timeout=10)
                with pytest.raises(TimeoutError):
                    mutation.result(timeout=0.15)
            finally:
                release.set()
            snapshot = original.result(timeout=20)
            saved = mutation.result(timeout=20)
            assert snapshot.event_page.total == 0 and snapshot.events == []
    finally:
        release.set()
        event.remove(engine, "after_cursor_execute", pause_after_count)
    with Session(engine) as db:
        current = EmployeeDayRead.model_validate(read_employee_day(db, institute, employee, day))
        assert current.event_page.total == 1 and current.events[0].id == saved.id
