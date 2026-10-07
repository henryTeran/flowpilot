from datetime import timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Event
import pytest
from fastapi import HTTPException
from sqlalchemy import event
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.appointments.models import Appointment
from app.modules.crm import return_sources
from app.modules.planning.models import ServiceSession
from app.modules.employees.models import Employee
from app.modules.tickets.models import TicketLine
from app.modules.tickets.repository import lock_institute
from test_crm_billing_12b import NOW, seed
from test_postgres_scheduling_4d import postgres_flow
from test_ticket_workflow import _auth_headers, _bootstrap_reference_data


def sources(db, institute, employee, service):
    seed(db, institute)
    base = NOW-timedelta(hours=6)
    for index in range(105):
        db.add(TicketLine(id=f"care_line_{index}", ticket_id=f"crm_{index}", service_id=service,
            quantity=1, duration_minutes=1))
    db.flush()
    for index in range(105):
        began = base+timedelta(minutes=index*2)
        db.add(ServiceSession(id=f"care_{index}", institute_id=institute, employee_id=employee,
            ticket_line_id=f"care_line_{index}", service_id=service, status="completed", start_time=began,
            planned_end_time=began+timedelta(minutes=1), real_end_time=began+timedelta(minutes=1), duration_minutes=1))
    db.add(ServiceSession(id="extra_care", institute_id=institute, employee_id=employee,
        ticket_line_id="care_line_0", service_id=service, status="completed", start_time=base+timedelta(seconds=10),
        planned_end_time=base+timedelta(seconds=50), real_end_time=base+timedelta(seconds=50), duration_minutes=1))
    began = base+timedelta(minutes=215)
    db.add(Appointment(id="care_return", institute_id=institute, customer_id="customer_crm", customer_name="Same Name",
        employee_id=employee, service_id=service, status="completed", checkout_ticket_id="eur",
        start_time=began, end_time=began+timedelta(minutes=1), actual_start_time=began, actual_end_time=began+timedelta(minutes=1)))
    db.commit()


def exercise(engine, institute, employee, service, monkeypatch):
    monkeypatch.setattr(return_sources, "utcnow", lambda: NOW)
    with Session(engine) as db:
        sources(db, institute, employee, service)
        start = NOW-timedelta(days=1)
        statements = []
        def track(conn, cursor, statement, parameters, context, executemany): statements.append(statement)
        event.listen(engine, "before_cursor_execute", track)
        try: value = return_sources.read(db, institute, "customer_crm", start, NOW)
        finally: event.remove(engine, "before_cursor_execute", track)
        assert len(statements) == 3
        assert value.complete_execution_coverage is False and value.complete_service_coverage is False
        assert value.page.total == value.summary.episode_count == 106
        assert value.summary.execution_count == 107 and len(value.episodes) == 20
        assert value.summary.average_return_gap_us.model_dump() == {"numerator": "6600000000", "denominator": "105"}
        final = return_sources.read(db, institute, "customer_crm", start, NOW, 20, 100)
        assert final.summary == value.summary and len(final.episodes) == 6 and len(final.gaps) == 6
        assert final.episodes[-1].ticket_id == "eur"
        zone = timezone(timedelta(hours=2))
        assert return_sources.read(db, institute, "customer_crm", start.astimezone(zone), NOW.astimezone(zone)).episodes == value.episodes
        appointment = db.get(Appointment, "care_return")
        appointment.checkout_ticket_id = None
        db.get(ServiceSession, "care_0").real_end_time = None
        db.get(ServiceSession, "care_1").real_end_time = NOW+timedelta(microseconds=1)
        db.commit()
        damaged = return_sources.read(db, institute, "customer_crm", start, NOW)
        assert damaged.diagnostics == {"unlinked_ticket": 1, "invalid_owner_or_service": 0, "invalid_actual_times": 2}
        assert damaged.summary.average_return_gap_us is None
        appointment.checkout_ticket_id = "other"
        db.add(Employee(id="care_foreign_employee", institute_id="crm_foreign", first_name="Foreign", skills=[], status="available"))
        db.flush()
        db.get(ServiceSession, "care_2").employee_id = "care_foreign_employee"
        db.commit()
        foreign = return_sources.read(db, institute, "customer_crm", start, NOW)
        assert foreign.diagnostics["invalid_owner_or_service"] == 2
        assert foreign.summary.average_return_gap_us is None
        for customer in ("customer_foreign", "historical_opaque", "missing"):
            with pytest.raises(HTTPException) as error: return_sources.read(db, institute, customer, start, NOW)
            assert error.value.status_code == 404


def test_sqlite_completed_care_cohort_and_bounded_rows(client, monkeypatch):
    institute, employees, services = _bootstrap_reference_data(client)
    exercise(main_module.engine, institute, employees[0]["id"], services[0]["id"], monkeypatch)


def test_postgres_completed_care_cohort_and_bounded_rows(postgres_flow, monkeypatch):
    exercise(*postgres_flow, monkeypatch)


def test_signed_return_cycle_scope_period_and_page(client, monkeypatch):
    institute, employees, services = _bootstrap_reference_data(client)
    monkeypatch.setattr(return_sources, "utcnow", lambda: NOW)
    with Session(main_module.engine) as db: sources(db, institute, employees[0]["id"], services[0]["id"])
    path = f"/api/v1/crm/institutes/{institute}/customers/customer_crm/return-cycle"
    params = {"start": (NOW-timedelta(days=1)).isoformat(), "end": NOW.isoformat()}
    headers = _auth_headers("responsable_institut", institute)
    response = client.get(path, params=params, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["summary"]["execution_count"] == 107 and len(response.json()["episodes"]) == 20
    for role, tenant in (("accueil", institute), ("collaboratrice", institute), ("responsable_institut", "foreign")):
        assert client.get(path, params=params, headers=_auth_headers(role, tenant)).status_code == 403
    assert client.get(path, params=params).status_code == 403
    assert client.get(path, params={**params, "start": "2026-10-06"}, headers=headers).status_code == 400
    assert client.get(path, params={**params, "limit": 51}, headers=headers).status_code == 422
    assert client.get(path, params={**params, "offset": -1}, headers=headers).status_code == 422


def test_postgres_return_snapshot_holds_shared_lock_until_complete_capture(postgres_flow, monkeypatch):
    engine, institute, employee, service = postgres_flow
    monkeypatch.setattr(return_sources, "utcnow", lambda: NOW)
    with Session(engine) as db: sources(db, institute, employee, service)
    paused, release, attempted = Event(), Event(), Event()
    def observe(connection, cursor, statement, parameters, context, executemany):
        if connection.info.get("return_reader") and "UNION ALL" in statement and not paused.is_set():
            paused.set(); assert release.wait(timeout=15)
        if not connection.info.get("return_reader") and "FROM institutes" in statement and "FOR UPDATE" in statement:
            attempted.set()
    def reader():
        with Session(engine) as db:
            connection = db.connection(); connection.info["return_reader"] = True
            try: return return_sources.read(db, institute, "customer_crm", NOW-timedelta(days=1), NOW)
            finally: connection.info.pop("return_reader", None)
    def writer():
        with Session(engine) as db:
            lock_institute(db, institute)
            db.get(ServiceSession, "care_0").status = "cancelled"
            db.commit()
    event.listen(engine, "before_cursor_execute", observe)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            reading = pool.submit(reader); assert paused.wait(timeout=10)
            writing = pool.submit(writer); assert attempted.wait(timeout=10)
            try:
                with pytest.raises(TimeoutError): writing.result(timeout=0.2)
            finally: release.set()
            snapshot = reading.result(timeout=15); writing.result(timeout=15)
        assert snapshot.summary.execution_count == 107
        with Session(engine) as db:
            assert return_sources.read(db, institute, "customer_crm", NOW-timedelta(days=1), NOW).summary.execution_count == 106
    finally:
        release.set(); event.remove(engine, "before_cursor_execute", observe)
