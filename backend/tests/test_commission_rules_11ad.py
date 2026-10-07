from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from threading import Barrier
import pytest
from fastapi import HTTPException
from sqlalchemy import event, select
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.institutes.models import Institute
from app.modules.workforce import commission_rules as rules
from app.modules.workforce.commission_rule_schemas import CommissionRuleCreate, CommissionRuleCancel, CommissionRulePage, calculation_terms
from app.modules.workforce.models import EmployeeCommissionRule
from test_workforce_absences_11b import setup
from test_ticket_workflow import _auth_headers
from test_postgres_scheduling_4d import postgres_flow


def payload(employee, service=None, key="rule-original"):
    return dict(employee_id=employee, title="Explicit recorded gross rule", basis="closed_attributed_line_gross", currency="CHF",
        category="care", service_id=service, rate_basis_points=1000, rounding="half_even", first_day="2026-10-25", last_day="2026-10-25",
        reason="Configured by signed manager", idempotency_key=key)


def exercise(engine, institute, employee, service, monkeypatch):
    with Session(engine) as db:
        db.get(Institute, institute).timezone = "Europe/Zurich"; db.commit()
        body = CommissionRuleCreate.model_validate(payload(employee, service))
        original = rules.create(db, institute, body, "signed")
        assert original.period_end-original.period_start == timedelta(hours=25)
        assert calculation_terms(original).rate_basis_points == 1000 and original.actor_id == "signed"
        db.get(Institute, institute).timezone = "Pacific/Apia"; db.commit()
        monkeypatch.setattr(rules, "utcnow", lambda: datetime(2020, 1, 1, tzinfo=timezone.utc))
        assert rules.create(db, institute, body, "signed") == original
        for changes in [dict(rate_basis_points=2000), dict(rounding="down"), dict(service_id=None), dict(currency="EUR"), dict(reason="Changed")]:
            with pytest.raises(HTTPException): rules.create(db, institute, CommissionRuleCreate.model_validate({**payload(employee, service), **changes}), "signed")
        with pytest.raises(HTTPException): rules.create(db, institute, body, "another")
        with pytest.raises(HTTPException): rules.create(db, institute, body, " ")
        assert rules.original(db, institute, "missing") is None and rules.original(db, "foreign", body.idempotency_key) is None
        with pytest.raises(HTTPException): rules.cancel(db, institute, original.id, CommissionRuleCancel(reason="Regressed clock", idempotency_key="regressed"), "signed")
        monkeypatch.setattr(rules, "utcnow", lambda: original.created_at+timedelta(microseconds=1))
        cancelled = rules.cancel(db, institute, original.id, CommissionRuleCancel(reason="Explicit correction", idempotency_key="rule-cancel"), "signed")
        monkeypatch.setattr(rules, "utcnow", lambda: datetime(2020, 1, 1, tzinfo=timezone.utc))
        assert rules.cancel(db, institute, original.id, CommissionRuleCancel(reason="Explicit correction", idempotency_key="rule-cancel"), "signed") == cancelled
        for terms, actor in [(dict(reason="Changed", idempotency_key="rule-cancel"), "signed"),
            (dict(reason="Explicit correction", idempotency_key="rule-cancel"), "another"), (dict(reason="Again", idempotency_key="new-cancel"), "signed")]:
            with pytest.raises(HTTPException): rules.cancel(db, institute, original.id, CommissionRuleCancel(**terms), actor)
        retained = rules.create(db, institute, body, "signed")
        assert retained.cancellation == cancelled
        assert retained.model_dump(exclude={"cancellation"}) == original.model_dump(exclude={"cancellation"})
        # Rules can overlap explicitly; future accruals must independently protect active source uniqueness.
        for index in range(22):
            rules.create(db, institute, CommissionRuleCreate.model_validate(payload(employee, key=f"rule-{index}")), "signed")
        queries = []
        def observe(_connection, _cursor, statement, _parameters, _context, _many):
            if statement.lstrip().upper().startswith("SELECT"): queries.append(statement)
        event.listen(engine, "before_cursor_execute", observe)
        try: page = CommissionRulePage.model_validate(rules.list_records(db, institute, employee))
        finally: event.remove(engine, "before_cursor_execute", observe)
        assert page.page.total == 23 and len(page.rows) == 20 and len(queries) <= 6
        second = CommissionRulePage.model_validate(rules.list_records(db, institute, employee, offset=20))
        assert len(second.rows) == 3 and len({row.id for row in page.rows+second.rows}) == 23
        with pytest.raises(HTTPException): rules.require(db, "foreign", original.id)
        with pytest.raises(HTTPException): rules.list_records(db, institute, "foreign")


def test_sqlite_original_commission_rule_replay_cancellation_and_bounded_history(client, monkeypatch):
    institute, employee, service, _, _ = setup(client)
    exercise(main_module.engine, institute, employee, service, monkeypatch)


def test_actual_postgres_original_commission_rules(postgres_flow, monkeypatch):
    exercise(*postgres_flow, monkeypatch)


def test_signed_rule_routes_scope_validation_and_empty_calendar(client):
    institute, employee, service, base, headers = setup(client)
    body = payload(employee, service)
    reply = client.post(base+"/commission-rules", headers=headers, json=body)
    assert reply.status_code == 200, reply.text
    original = reply.json(); identifier = original["id"]
    assert original["actor_id"] == "test-user"
    assert client.get(base+"/commission-rules/original/rule-original", headers=headers).json() == original
    assert client.get(base+f"/commission-rules/{identifier}", headers=headers).json() == original
    cancel = client.post(base+f"/commission-rules/{identifier}/cancel", headers=headers, json=dict(reason="Correction", idempotency_key="signed-cancel"))
    assert cancel.status_code == 200, cancel.text
    assert client.get(base+"/commission-rule-cancellations/original/signed-cancel", headers=headers).json() == cancel.json()
    assert client.get(base+"/commission-rule-cancellations/original/missing", headers=headers).json() is None
    assert client.get(base+f"/employees/{employee}/commission-rules", headers=headers).json()["rows"][0]["cancellation"] == cancel.json()
    for role, scope in [("accueil", institute), ("responsable_institut", "foreign")]:
        denied = _auth_headers(role, scope)
        for path in ["/commission-rules/original/rule-original", f"/commission-rules/{identifier}", "/commission-rule-cancellations/original/signed-cancel", f"/employees/{employee}/commission-rules"]:
            assert client.get(base+path, headers=denied).status_code == 403
        assert client.post(base+"/commission-rules", headers=denied, json=body).status_code == 403
        assert client.post(base+f"/commission-rules/{identifier}/cancel", headers=denied, json=dict(reason="Denied", idempotency_key="denied")).status_code == 403
    for changes in [dict(rate_basis_points=True), dict(rate_basis_points="1000"), dict(rate_basis_points=1.5), dict(rate_basis_points=10001),
        dict(rate_basis_points=-1), dict(currency=None), dict(rounding="default"), dict(first_day="2026-10-25T00:00:00Z"),
        dict(first_day="2026-10-26"), dict(period_start="2026-10-25T00:00:00Z"), dict(basis="net")]:
        assert client.post(base+"/commission-rules", headers=headers, json={**body, **changes, "idempotency_key": "invalid"}).status_code == 422
    assert client.post(base+"/commission-rules", headers=headers, json={**body, "employee_id": "foreign", "idempotency_key": "foreign"}).status_code == 404
    assert client.post(base+"/commission-rules", headers=headers, json={**body, "service_id": "missing", "idempotency_key": "missing"}).status_code == 404
    assert client.get(base+f"/employees/{employee}/commission-rules?limit=51", headers=headers).status_code == 422
    with Session(main_module.engine) as db:
        db.get(Institute, institute).timezone = "Europe/Zurich"; db.commit()
    spring = client.post(base+"/commission-rules", headers=headers, json={**body, "first_day": "2026-03-29", "last_day": "2026-03-29", "rate_basis_points": 0, "idempotency_key": "spring-zero"})
    assert spring.status_code == 200, spring.text
    value = spring.json()
    assert datetime.fromisoformat(value["period_end"])-datetime.fromisoformat(value["period_start"]) == timedelta(hours=23)
    assert value["rate_basis_points"] == 0
    with Session(main_module.engine) as db:
        db.get(Institute, institute).timezone = "Pacific/Apia"; db.commit()
    for first, last in [("2011-12-30", "2011-12-30"), ("9999-12-31", "9999-12-31")]:
        assert client.post(base+"/commission-rules", headers=headers, json={**body, "first_day": first, "last_day": last, "idempotency_key": "empty"}).status_code == 400


def test_actual_postgres_concurrent_rule_replay(postgres_flow):
    engine, institute, employee, service = postgres_flow
    barrier = Barrier(2); body = CommissionRuleCreate.model_validate(payload(employee, service))
    def writer():
        with Session(engine) as db:
            barrier.wait(timeout=10)
            return rules.create(db, institute, body, "signed").id
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(writer) for _ in range(2)]
        identifiers = [future.result(timeout=20) for future in futures]
    assert identifiers[0] == identifiers[1]
    with Session(engine) as db: assert len(list(db.scalars(select(EmployeeCommissionRule)))) == 1
    cancel_barrier = Barrier(2)
    def cancel_writer():
        with Session(engine) as db:
            cancel_barrier.wait(timeout=10)
            return rules.cancel(db, institute, identifiers[0], CommissionRuleCancel(reason="Concurrent correction", idempotency_key="race-cancel"), "signed").id
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(cancel_writer) for _ in range(2)]
        cancellations = [future.result(timeout=20) for future in futures]
    assert cancellations[0] == cancellations[1]
