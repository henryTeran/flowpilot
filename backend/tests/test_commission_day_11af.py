from datetime import date, timedelta
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Event
import pytest
from sqlalchemy import event, select
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.institutes.models import Institute
from app.modules.tickets.models import TicketLine, QueueTicket
from app.modules.workforce import commissions as ledger, commission_day as day_read
from app.modules.workforce.absence_schemas import AbsenceCancel
from app.modules.workforce.models import EmployeeCommission, CommissionCancellation
from app.modules.workforce import commission_rules as rules
from app.modules.workforce.commission_rule_schemas import CommissionRuleCreate
from test_commission_rules_11ad import payload as rule_payload
from test_commissions_11ae import NOW, fixture, body
from test_workforce_absences_11b import setup
from test_postgres_scheduling_4d import postgres_flow
from test_ticket_workflow import _auth_headers


def exercise(engine, institute, employee, service, monkeypatch):
    first, _ = fixture(engine, institute, employee, service, monkeypatch)
    monkeypatch.setattr(day_read, "utcnow", lambda: NOW)
    with Session(engine) as db:
        db.get(Institute, institute).timezone = "Europe/Zurich"; db.commit()
        original = ledger.create(db, institute, body(first), "manager")
        def read(day=date(2026, 10, 25), offset=0): return day_read.read(db, institute, employee, day, offset=offset)
        value = read()
        assert value.end-value.start == timedelta(hours=25) and value.rows[0].original == original
        assert value.counts["recorded"] == 1 and value.currencies[0].amounts_minor["recorded"] == "104"
        assert value.complete_entitlement is False and value.payable_total is None and value.basis == "commission_recorded_at"
        line = db.get(TicketLine, "commission-line"); line.total = Decimal("999.99"); db.commit()
        assert read().currencies[0].amounts_minor["recorded"] == "104"
        monkeypatch.setattr(day_read, "utcnow", lambda: NOW-timedelta(microseconds=1))
        assert read().counts["future_recording"] == 1 and read().currencies[0].amounts_minor["recorded"] == "0"
        monkeypatch.setattr(ledger, "utcnow", lambda: NOW+timedelta(microseconds=1))
        cancelled = ledger.cancel(db, institute, original.id, AbsenceCancel(reason="Explicit correction", idempotency_key="day-cancel"), "manager")
        monkeypatch.setattr(day_read, "utcnow", lambda: NOW)
        assert read().counts["future_cancellation"] == 1
        monkeypatch.setattr(day_read, "utcnow", lambda: NOW+timedelta(microseconds=1))
        assert read().counts["cancelled"] == 1 and read().currencies[0].amounts_minor["cancelled"] == "104"
        euro_rule = rules.create(db, institute, CommissionRuleCreate.model_validate({**rule_payload(employee, service, "euro-rule"), "currency": "EUR", "rounding": "half_up"}), "manager")
        db.get(QueueTicket, original.ticket_id).currency = "EUR"
        db.add(TicketLine(id="euro-line", ticket_id=original.ticket_id, service_id=service, quantity=1, duration_minutes=10,
            total=Decimal("0.15"), performed_by_employee_id=employee, revenue_category="care")); db.commit()
        ledger.create(db, institute, body(euro_rule, "euro-original", "euro-line"), "manager")
        # Retained cancelled correction history; no duplicate active source credit.
        for index in range(21):
            identifier = f"commission-history-{index}"
            db.add(EmployeeCommission(id=identifier, institute_id=institute, employee_id=employee, rule_id=first.id,
                ticket_id=original.ticket_id, line_id=original.line_id, currency="CHF", amount_minor="104",
                rule_capture=original.rule_capture.model_dump(mode="json"), calculation=original.calculation.model_dump(mode="json"),
                actor_id="manager", reason="Retained correction", idempotency_key=identifier, created_at=NOW)); db.flush()
            db.add(CommissionCancellation(id=f"cancel-{identifier}", institute_id=institute, commission_id=identifier,
                actor_id="manager", reason="Correction", idempotency_key=f"cancel-{identifier}", created_at=cancelled.created_at))
        db.commit()
        queries = []
        def observe(_c, _cursor, statement, _p, _ctx, _many):
            if statement.lstrip().upper().startswith("SELECT"): queries.append(statement)
        event.listen(engine, "before_cursor_execute", observe)
        try: value = read()
        finally: event.remove(engine, "before_cursor_execute", observe)
        assert value.page.total == 23 and len(value.rows) == 20 and value.counts["cancelled"] == 22 and value.counts["recorded"] == 1
        assert value.currencies[0].amounts_minor["cancelled"] == "2288" and len(queries) <= 6
        assert value.currencies[1].currency == "EUR" and value.currencies[1].amounts_minor["recorded"] == "2"
        assert len(read(offset=20).rows) == 3 and read(offset=40).page.total == 23
        assert read(date(2026, 10, 26)).page.total == 0
        # Real writes at exact civil boundaries: start included, end on next day.
        start, end = value.start, value.end
        monkeypatch.setattr(rules, "utcnow", lambda: start-timedelta(hours=2))
        start_rule = rules.create(db, institute, CommissionRuleCreate.model_validate({**rule_payload(employee, service, "start-rule"), "rate_basis_points": 10000}), "manager")
        db.add(QueueTicket(id="start-ticket", institute_id=institute, ticket_number="START", status="paid", currency="CHF",
            arrival_time=start-timedelta(hours=1), paid_at=start)); db.flush()
        db.add(TicketLine(id="start-line", ticket_id="start-ticket", service_id=service, quantity=1, duration_minutes=10,
            total=Decimal("0.01"), performed_by_employee_id=employee, revenue_category="care")); db.commit()
        monkeypatch.setattr(ledger, "utcnow", lambda: start)
        ledger.create(db, institute, body(start_rule, "start-original", "start-line"), "manager")
        assert read().page.total == 24 and read().currencies[0].amounts_minor["recorded"] == "1"
        assert read(date(2026, 10, 24)).page.total == 0
        db.add(TicketLine(id="end-line", ticket_id=original.ticket_id, service_id=service, quantity=1, duration_minutes=10,
            total=Decimal("0.15"), performed_by_employee_id=employee, revenue_category="care")); db.commit()
        monkeypatch.setattr(ledger, "utcnow", lambda: end)
        ledger.create(db, institute, body(euro_rule, "end-original", "end-line"), "manager")
        assert read().page.total == 24 and read(date(2026, 10, 26)).page.total == 1
        assert read(date(2026, 10, 26)).counts["future_recording"] == 1
        assert read(date(2026, 3, 29)).end-read(date(2026, 3, 29)).start == timedelta(hours=23)
        db.get(Institute, institute).timezone = "Pacific/Apia"; db.commit()
        skipped = read(date(2011, 12, 30)); assert skipped.start == skipped.end and skipped.page.total == 0 and skipped.currencies == []


def test_sqlite_recorded_commission_day_exact_totals_states_and_http_scope(client, monkeypatch):
    institute, employee, service, base, headers = setup(client)
    exercise(main_module.engine, institute, employee, service, monkeypatch)
    path = base+f"/employees/{employee}/commission-day?day=2026-10-25"
    assert client.get(path, headers=headers).status_code == 200
    assert client.get(path, headers=_auth_headers("accueil", institute)).status_code == 403
    assert client.get(path, headers=_auth_headers("responsable_institut", "foreign")).status_code == 403
    assert client.get(path+"&limit=51", headers=headers).status_code == 422
    assert client.get(base+"/employees/foreign/commission-day?day=2026-10-25", headers=headers).status_code == 404
    assert client.get(base+f"/employees/{employee}/commission-day?day=9999-12-31", headers=headers).status_code == 400


def test_actual_postgres_recorded_commission_day(postgres_flow, monkeypatch):
    exercise(*postgres_flow, monkeypatch)


def test_actual_postgres_commission_day_serialized_snapshot(postgres_flow, monkeypatch):
    engine, institute, employee, service = postgres_flow
    first, _ = fixture(engine, institute, employee, service, monkeypatch)
    monkeypatch.setattr(day_read, "utcnow", lambda: NOW)
    paused, release, attempted = Event(), Event(), Event()
    def observe(connection, _cursor, statement, _p, _ctx, _many):
        if connection.info.get("commission_reader") and "FROM employee_commissions" in statement and not paused.is_set():
            paused.set(); assert release.wait(timeout=15)
        if not connection.info.get("commission_reader") and "FROM institutes" in statement and "FOR UPDATE" in statement:
            attempted.set()
    def reader():
        with Session(engine) as db:
            connection = db.connection(); connection.info["commission_reader"] = True
            try: return day_read.read(db, institute, employee, date(2026, 10, 25))
            finally: connection.info.pop("commission_reader", None)
    def writer():
        with Session(engine) as db: return ledger.create(db, institute, body(first), "manager")
    event.listen(engine, "before_cursor_execute", observe)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            reading = pool.submit(reader); assert paused.wait(timeout=10)
            writing = pool.submit(writer); assert attempted.wait(timeout=10)
            try:
                with pytest.raises(TimeoutError): writing.result(timeout=0.2)
            finally: release.set()
            snapshot = reading.result(timeout=15); writing.result(timeout=15)
        assert snapshot.page.total == 0 and snapshot.rows == [] and snapshot.currencies == []
        with Session(engine) as db: assert day_read.read(db, institute, employee, date(2026, 10, 25)).counts["recorded"] == 1
    finally:
        release.set(); event.remove(engine, "before_cursor_execute", observe)
