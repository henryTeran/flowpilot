from datetime import date, timedelta
from decimal import Decimal
import pytest
from fastapi import HTTPException
from sqlalchemy import event, select
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.tickets.models import QueueTicket, TicketLine
from app.modules.institutes.models import Institute
from app.modules.services.models import Service
from app.modules.workforce.commission_rule_schemas import CommissionRuleCreate
from test_commission_rules_11ad import payload as rule_payload
from app.modules.workforce import commission_options as choices, commissions as ledger, commission_rules as rules
from app.modules.workforce.absence_schemas import AbsenceCancel
from app.modules.workforce.commission_rule_schemas import CommissionRuleCancel
from test_commissions_11ae import NOW, fixture, body
from test_workforce_absences_11b import setup
from test_postgres_scheduling_4d import postgres_flow
from test_ticket_workflow import _auth_headers


def exercise(engine, institute, employee, service, monkeypatch):
    first, second = fixture(engine, institute, employee, service, monkeypatch)
    monkeypatch.setattr(choices, "utcnow", lambda: NOW)
    with Session(engine) as db:
        db.get(Institute, institute).timezone = "Europe/Zurich"; db.commit()
        def read(day=date(2026, 10, 25), offset=0): return choices.read(db, institute, first.id, day, offset=offset)
        value = read(); assert value.page.total == 1 and value.rows[0].exclusion is None
        assert value.rows[0].ticket_number == db.get(QueueTicket, value.rows[0].ticket_id).ticket_number
        assert value.rows[0].calculation.amount_minor == "104" and value.rule == first
        assert value.end-value.start == timedelta(hours=25) and value.complete_sources is False and value.basis == "source_closed_day"
        # Cross-rule active attribution disables the same source; cancellation releases it.
        original = ledger.create(db, institute, body(second), "manager")
        assert read().rows[0].exclusion == "already_attributed" and read().rows[0].calculation is None
        monkeypatch.setattr(ledger, "utcnow", lambda: NOW+timedelta(microseconds=1))
        ledger.cancel(db, institute, original.id, AbsenceCancel(reason="Explicit correction", idempotency_key="choice-cancel"), "manager")
        assert read().rows[0].exclusion == "future_cancellation" and read().rows[0].cancellation_clock_future is True
        monkeypatch.setattr(ledger, "utcnow", lambda: NOW)
        with pytest.raises(HTTPException) as failure: ledger.create(db, institute, body(first, "before-cancel-clock"), "manager")
        assert failure.value.status_code == 400
        monkeypatch.setattr(ledger, "utcnow", lambda: NOW+timedelta(microseconds=1))
        monkeypatch.setattr(choices, "utcnow", lambda: NOW+timedelta(microseconds=1))
        assert read().rows[0].exclusion is None
        line = db.get(TicketLine, "commission-line"); ticket = db.get(QueueTicket, "commission-ticket")
        for target, field, invalid, expected in [(line, "total", None, "invalid_source"),
            (line, "total", Decimal("-1"), "invalid_source"), (line, "total", Decimal("NaN"), "invalid_source"),
            (line, "total", 1.23, "invalid_source"), (line, "quantity", 0, "invalid_source"),
            (ticket, "currency", None, "currency_mismatch"), (ticket, "currency", "EUR", "currency_mismatch"),
            (ticket, "paid_at", NOW+timedelta(microseconds=2), "future_closing"),
            (ticket, "arrival_time", NOW, "invalid_source")]:
            previous = getattr(target, field); setattr(target, field, invalid); db.flush()
            item = read().rows[0]; assert item.exclusion == expected and item.calculation is None
            setattr(target, field, previous); db.flush()
        for target, field, invalid in [(ticket, "paid_at", None), (ticket, "status", "in_checkout"),
            (line, "performed_by_employee_id", None), (line, "performed_by_employee_id", "unknown"), (line, "revenue_category", "product")]:
            previous = getattr(target, field); setattr(target, field, invalid); db.flush()
            assert read().page.total == 0
            setattr(target, field, previous); db.flush()
        line.invoice_removed_at = NOW; line.invoice_removed_by_actor = "manager"; line.invoice_removal_reason = "not_performed"; db.flush()
        assert read().page.total == 0
        line.invoice_removed_at = line.invoice_removed_by_actor = line.invoice_removal_reason = None; db.flush()
        start, end = value.start, value.end
        ticket.paid_at = start; ticket.arrival_time = start-timedelta(hours=1); db.flush()
        assert read().page.total == 1 and read().rows[0].exclusion is None
        ticket.paid_at = end; db.flush()
        assert read().page.total == 0 and read(date(2026, 10, 26)).rows[0].exclusion == "future_closing"
        monkeypatch.setattr(choices, "utcnow", lambda: end+timedelta(hours=1))
        assert read(date(2026, 10, 26)).rows[0].exclusion == "outside_period"
        ticket.paid_at = NOW-timedelta(hours=1); ticket.arrival_time = NOW-timedelta(hours=3); db.flush()
        monkeypatch.setattr(choices, "utcnow", lambda: NOW-timedelta(hours=3))
        assert read().rows[0].exclusion == "future_rule"
        monkeypatch.setattr(choices, "utcnow", lambda: NOW+timedelta(microseconds=1))
        for index in range(26):
            db.add(TicketLine(id=f"choice-{index}", ticket_id=ticket.id, service_id=service, quantity=1, duration_minutes=10,
                total=Decimal("0.10"), performed_by_employee_id=employee, revenue_category="care"))
        db.commit()
        queries = []
        def observe(_c, _cursor, statement, _p, _ctx, _many):
            if statement.lstrip().upper().startswith("SELECT"): queries.append(statement)
        event.listen(engine, "before_cursor_execute", observe)
        try: page = read()
        finally: event.remove(engine, "before_cursor_execute", observe)
        second_page = read(offset=20)
        assert page.page.total == 27 and len(page.rows) == 20 and len(second_page.rows) == 7 and len(queries) <= 8
        assert len({item.line_id for item in page.rows+second_page.rows}) == 27
        assert all(item.calculation is not None for item in page.rows+second_page.rows)
        other_service = db.scalar(select(Service.id).where(Service.id != service))
        assert other_service
        db.add(TicketLine(id="other-service-line", ticket_id=ticket.id, service_id=other_service, quantity=1, duration_minutes=10,
            total=Decimal("0.20"), performed_by_employee_id=employee, revenue_category="care")); db.commit()
        assert read().page.total == 27
        all_services = rules.create(db, institute, CommissionRuleCreate.model_validate(rule_payload(employee, None, "all-services")), "manager")
        broad = choices.read(db, institute, all_services.id, date(2026, 10, 25), limit=50)
        assert broad.page.total == 28
        assert next(item for item in broad.rows if item.line_id == "other-service-line").calculation.source.service_id == other_service
        rules.cancel(db, institute, first.id, CommissionRuleCancel(reason="Stop new accruals", idempotency_key="stop-rule"), "manager")
        assert all(item.exclusion == "rule_cancelled" and item.calculation is None for item in read().rows)
        assert read(date(2026, 3, 29)).end-read(date(2026, 3, 29)).start == timedelta(hours=23)
        db.get(Institute, institute).timezone = "Pacific/Apia"; db.commit()
        skipped = read(date(2011, 12, 30)); assert skipped.start == skipped.end and skipped.page.total == 0
        return first.id


def test_sqlite_rule_source_choices_exact_guards_and_signed_scope(client, monkeypatch):
    institute, employee, service, base, headers = setup(client)
    identifier = exercise(main_module.engine, institute, employee, service, monkeypatch)
    path = base+f"/commission-rules/{identifier}/sources?day=2026-10-25"
    assert client.get(path, headers=headers).status_code == 200
    assert client.get(path, headers=_auth_headers("accueil", institute)).status_code == 403
    assert client.get(path, headers=_auth_headers("responsable_institut", "foreign")).status_code == 403
    assert client.get(path+"&limit=51", headers=headers).status_code == 422
    assert client.get(base+"/commission-rules/missing/sources?day=2026-10-25", headers=headers).status_code == 404
    assert client.get(base+f"/commission-rules/{identifier}/sources?day=9999-12-31", headers=headers).status_code == 400


def test_actual_postgres_rule_source_choices(postgres_flow, monkeypatch):
    exercise(*postgres_flow, monkeypatch)
