from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from threading import Barrier
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import event, select
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.tickets.models import QueueTicket, TicketLine
from app.modules.workforce import commission_rules as rules, commissions as ledger
from app.modules.workforce.commission_rule_schemas import CommissionRuleCreate, CommissionRuleCancel
from app.modules.workforce.absence_schemas import AbsenceCancel
from test_commission_rules_11ad import payload as rule_payload
from test_workforce_absences_11b import setup
from test_ticket_workflow import _auth_headers
from test_postgres_scheduling_4d import postgres_flow

NOW = datetime(2026, 10, 25, 12, tzinfo=timezone.utc)


def fixture(engine, institute, employee, service, monkeypatch):
    monkeypatch.setattr(rules, "utcnow", lambda: NOW-timedelta(hours=2))
    monkeypatch.setattr(ledger, "utcnow", lambda: NOW)
    with Session(engine) as db:
        first = rules.create(db, institute, CommissionRuleCreate.model_validate({**rule_payload(employee, service), "rounding": "half_up"}), "manager")
        second = rules.create(db, institute, CommissionRuleCreate.model_validate({**rule_payload(employee, service, "alternative"), "rate_basis_points": 2000}), "manager")
        ticket = QueueTicket(id="commission-ticket", institute_id=institute, ticket_number="C1", status="paid", currency="CHF",
            arrival_time=NOW-timedelta(hours=3), paid_at=NOW-timedelta(hours=1), paid_employee_id="cashier")
        db.add(ticket); db.flush()
        db.add(TicketLine(id="commission-line", ticket_id=ticket.id, service_id=service, quantity=3, duration_minutes=10,
            total=Decimal("10.35"), performed_by_employee_id=employee, revenue_category="care")); db.commit()
    return first, second


def body(rule, key="commission-original", line="commission-line"):
    return ledger.CommissionCreate(rule_id=rule.id, line_id=line, reason="Explicit calculated commission", idempotency_key=key)


def exercise(engine, institute, employee, service, monkeypatch):
    first, second = fixture(engine, institute, employee, service, monkeypatch)
    with Session(engine) as db:
        original = ledger.create(db, institute, body(first), "manager")
        assert original.calculation.amount_minor == "104" and original.calculation.source.quantity == 3
        assert original.rule_capture == first and original.employee_id == employee
        for request, actor in [(body(first, "duplicate"), "manager"), (body(second, "overlap"), "manager"),
            (body(second), "manager"), (body(first), "other")]:
            with pytest.raises(HTTPException): ledger.create(db, institute, request, actor)
        changed = original.model_dump(); changed["calculation"]["amount_minor"] = "103"
        with pytest.raises(ValidationError): ledger.CommissionRead.model_validate(changed)
        changed = original.model_dump(); changed["rule_capture"]["rate_basis_points"] = 2000
        with pytest.raises(ValidationError): ledger.CommissionRead.model_validate(changed)
        changed = original.model_dump(); changed["calculation"]["source"]["category"] = "product"
        with pytest.raises(ValidationError): ledger.CommissionRead.model_validate(changed)
        line = db.get(TicketLine, "commission-line"); line.total = Decimal("99.99"); line.quantity = 5
        ticket = db.get(QueueTicket, "commission-ticket"); ticket.currency = "EUR"; db.commit()
        monkeypatch.setattr(ledger, "utcnow", lambda: datetime(2020, 1, 1, tzinfo=timezone.utc))
        assert ledger.create(db, institute, body(first), "manager") == original
        assert ledger.original(db, institute, "commission-original") == original
        with pytest.raises(HTTPException): ledger.cancel(db, institute, original.id, AbsenceCancel(reason="Clock regression", idempotency_key="regression"), "manager")
        monkeypatch.setattr(ledger, "utcnow", lambda: NOW+timedelta(microseconds=1))
        monkeypatch.setattr(rules, "utcnow", lambda: NOW+timedelta(microseconds=1))
        rules.cancel(db, institute, first.id, CommissionRuleCancel(reason="Rule corrected", idempotency_key="rule-correction"), "manager")
        assert ledger.original(db, institute, "commission-original") == original  # Rule cancellation does not retract an accrual.
        cancel_terms = AbsenceCancel(reason="Accrual correction", idempotency_key="commission-cancel")
        cancelled = ledger.cancel(db, institute, original.id, cancel_terms, "manager")
        monkeypatch.setattr(ledger, "utcnow", lambda: datetime(2020, 1, 1, tzinfo=timezone.utc))
        assert ledger.cancel(db, institute, original.id, cancel_terms, "manager") == cancelled
        retained = ledger.create(db, institute, body(first), "manager")
        assert retained.cancellation == cancelled and retained.rule_capture == first and retained.calculation == original.calculation
        changed = retained.model_dump(); changed["cancellation"]["commission_id"] = "foreign"
        with pytest.raises(ValidationError): ledger.CommissionRead.model_validate(changed)
        for request, actor in [(cancel_terms, "other"), (AbsenceCancel(reason="Changed", idempotency_key="commission-cancel"), "manager"),
            (AbsenceCancel(reason="Again", idempotency_key="another"), "manager")]:
            with pytest.raises(HTTPException): ledger.cancel(db, institute, original.id, request, actor)
        monkeypatch.setattr(ledger, "utcnow", lambda: NOW+timedelta(microseconds=2))
        with pytest.raises(HTTPException): ledger.create(db, institute, body(first, "cancelled-rule"), "manager")
        line.total = Decimal("10.35"); line.quantity = 3; ticket.currency = "CHF"; db.commit()
        corrected = ledger.create(db, institute, body(second, "corrected"), "manager")
        assert corrected.calculation.amount_minor == "207" and corrected.id != original.id
        rules.cancel(db, institute, second.id, CommissionRuleCancel(reason="Stop further rule usage", idempotency_key="second-rule-stop"), "manager")
        third = rules.create(db, institute, CommissionRuleCreate.model_validate(rule_payload(employee, service, "third")), "manager")
        with pytest.raises(HTTPException): ledger.create(db, institute, body(third, "still-active"), "manager")
        assert ledger.original(db, institute, "missing") is None and ledger.original(db, "foreign", "corrected") is None
        with pytest.raises(HTTPException): ledger.require(db, "foreign", original.id)
        for index in range(21):
            db.add(TicketLine(id=f"page-line-{index}", ticket_id=ticket.id, service_id=service, quantity=1, duration_minutes=10,
                total=Decimal("0.10"), performed_by_employee_id=employee, revenue_category="care")); db.commit()
            ledger.create(db, institute, body(third, f"page-{index}", f"page-line-{index}"), "manager")
        queries = []
        def observe(_c, _cursor, statement, _p, _ctx, _many):
            if statement.lstrip().upper().startswith("SELECT"): queries.append(statement)
        event.listen(engine, "before_cursor_execute", observe)
        try: page = ledger.list_records(db, institute, employee)
        finally: event.remove(engine, "before_cursor_execute", observe)
        second_page = ledger.list_records(db, institute, employee, offset=20)
        assert page.page.total == 23 and len(page.rows) == 20 and len(second_page.rows) == 3 and len(queries) <= 6
        assert len({row.id for row in page.rows+second_page.rows}) == 23


def test_sqlite_original_commission_lifecycle_and_pinned_authorities(client, monkeypatch):
    institute, employee, service, _, _ = setup(client)
    exercise(main_module.engine, institute, employee, service, monkeypatch)


def test_actual_postgres_original_commission_lifecycle(postgres_flow, monkeypatch):
    exercise(*postgres_flow, monkeypatch)


def test_signed_commission_routes_original_recovery_scope_and_validation(client, monkeypatch):
    institute, employee, service, base, headers = setup(client)
    first, _ = fixture(main_module.engine, institute, employee, service, monkeypatch)
    request = body(first).model_dump()
    response = client.post(base+"/commissions", headers=headers, json=request)
    assert response.status_code == 200, response.text
    original = response.json(); identifier = original["id"]
    assert original["actor_id"] == "test-user" and original["calculation"]["amount_minor"] == "104"
    assert client.post(base+"/commissions", headers=headers, json=request).json() == original
    assert client.get(base+"/commissions/original/commission-original", headers=headers).json() == original
    assert client.get(base+f"/commissions/{identifier}", headers=headers).json() == original
    cancel = client.post(base+f"/commissions/{identifier}/cancel", headers=headers, json=dict(reason="Explicit correction", idempotency_key="cancel"))
    assert cancel.status_code == 200, cancel.text
    assert client.get(base+"/commission-cancellations/original/cancel", headers=headers).json() == cancel.json()
    assert client.get(base+"/commission-cancellations/original/missing", headers=headers).json() is None
    assert client.get(base+f"/employees/{employee}/commissions", headers=headers).json()["rows"][0]["cancellation"] == cancel.json()
    for role, scope in [("accueil", institute), ("responsable_institut", "foreign")]:
        denied = _auth_headers(role, scope)
        for path in ["/commissions/original/commission-original", f"/commissions/{identifier}", "/commission-cancellations/original/cancel", f"/employees/{employee}/commissions"]:
            assert client.get(base+path, headers=denied).status_code == 403
        assert client.post(base+"/commissions", headers=denied, json=request).status_code == 403
        assert client.post(base+f"/commissions/{identifier}/cancel", headers=denied, json=dict(reason="Denied", idempotency_key="denied")).status_code == 403
    assert client.post(base+"/commissions", headers=headers, json={**request, "amount_minor": "999"}).status_code == 422
    assert client.post(base+"/commissions", headers=headers, json={**request, "line_id": "foreign", "idempotency_key": "foreign"}).status_code == 404
    assert client.post(base+"/commissions", headers=headers, json={**request, "rule_id": "foreign", "idempotency_key": "foreign-rule"}).status_code == 404
    assert client.get(base+f"/employees/{employee}/commissions?limit=51", headers=headers).status_code == 422
    assert client.get(base+"/employees/foreign/commissions", headers=headers).status_code == 404


def test_actual_postgres_competing_active_source_and_same_key(postgres_flow, monkeypatch):
    engine, institute, employee, service = postgres_flow
    first, second = fixture(engine, institute, employee, service, monkeypatch)
    def compete(requests):
        barrier = Barrier(2)
        def writer(request):
            with Session(engine) as db:
                barrier.wait(timeout=10)
                try: return ledger.create(db, institute, request, "manager").id
                except HTTPException as error: return error.status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(writer, request) for request in requests]
            return [future.result(timeout=20) for future in futures]
    outcomes = compete([body(first, "one"), body(second, "two")])
    assert sum(isinstance(value, str) for value in outcomes) == 1 and 400 in outcomes
    with Session(engine) as db:
        winner = next(value for value in outcomes if isinstance(value, str))
        ledger.cancel(db, institute, winner, AbsenceCancel(reason="Race correction", idempotency_key="race-cancel"), "manager")
    replayed = compete([body(first, "same"), body(first, "same")])
    assert isinstance(replayed[0], str) and replayed[0] == replayed[1]
