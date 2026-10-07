from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from fastapi import HTTPException
from sqlalchemy import select, event
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import app.main as main_module
from app.modules.workforce import objectives
from app.modules.workforce.objective_schemas import ObjectiveCreate, ObjectiveCancel, ObjectivePage, ObjectiveRead
from app.modules.workforce.models import EmployeeObjective, ObjectiveCancellation
from app.modules.institutes.models import Institute
from app.modules.planning.models import ServiceSession
from app.shared.time import utcnow
from test_workforce_absences_11b import setup
from test_ticket_workflow import _auth_headers
from test_postgres_scheduling_4d import postgres_flow
from test_employee_revenue_11g import fixture as revenue_fixture


def payload(employee, key="gross"):
    return dict(employee_id=employee, title="Declared gross target", metric="closed_attributed_gross", currency="CHF",
                target="10.45", first_day="2026-10-25", last_day="2026-10-25", reason="Manager declared", idempotency_key=key)


def exercise(engine, institute, employee, service, monkeypatch):
    revenue_fixture(engine, institute, employee, service)
    with Session(engine) as db:
        original = objectives.create(db, institute, ObjectiveCreate.model_validate(payload(employee)), "signed")
        assert original.period_end-original.period_start == timedelta(hours=25)
        count = objectives.create(db, institute, ObjectiveCreate.model_validate({**payload(employee, "sessions"),
            "metric": "completed_sessions", "currency": None, "target": "1"}), "signed")
        for index, status, start, finish in [
            (0, "completed", original.period_start, original.period_start+timedelta(minutes=10)),
            (1, "planned", original.period_start, original.period_start+timedelta(minutes=10)),
            (2, "completed", original.period_end-timedelta(minutes=10), original.period_end),
            (3, "completed", original.period_start, None),
            (4, "completed", original.period_start+timedelta(minutes=10), original.period_start)]:
            db.add(ServiceSession(id=f"objective-session-{index}", institute_id=institute, employee_id=employee, service_id=service,
                start_time=start, planned_end_time=start+timedelta(minutes=10), real_end_time=finish, duration_minutes=10, status=status))
        db.get(Institute, institute).timezone = "UTC"
        db.commit()
        known_target = objectives.create(db, institute, ObjectiveCreate.model_validate({**payload(employee, "known"), "target": "77.10"}), "signed")
        replay = objectives.create(db, institute, ObjectiveCreate.model_validate(payload(employee)), "signed")
        assert replay.model_dump() == original.model_dump()  # Bounds retain declared timezone.
        monkeypatch.setattr(objectives, "utcnow", lambda: original.period_start+timedelta(minutes=5))
        early = ObjectivePage.model_validate(objectives.list_records(db, institute, employee))
        assert next(row for row in early.rows if row.objective.id == count.id).value == 0
        monkeypatch.setattr(objectives, "utcnow", lambda: original.period_end+timedelta(days=1))
        with localcontext() as context:
            context.prec = 2
            report = ObjectivePage.model_validate(objectives.list_records(db, institute, employee))
        gross = next(row for row in report.rows if row.objective.id == original.id)
        completed = next(row for row in report.rows if row.objective.id == count.id)
        known = next(row for row in report.rows if row.objective.id == known_target.id)
        assert gross.known_value == Decimal("10.45") and gross.value is None and gross.achieved is None
        assert gross.unknown_currency_sources == 1 and gross.other_currency_sources == 2 and gross.source_count == 5
        assert completed.value == 1 and completed.achieved is True and completed.source_count == 1
        assert known.value == Decimal("77.10") and known.achieved is True and known.source_count == 2
        assert known.objective.timezone == "UTC" and original.timezone == "Europe/Zurich"
        assert gross.period_state == completed.period_state == "ended"
        cancellation = objectives.cancel(db, institute, original.id, ObjectiveCancel(reason="Corrected target", idempotency_key="cancel"), "signed")
        assert objectives.cancel(db, institute, original.id, ObjectiveCancel(reason="Corrected target", idempotency_key="cancel"), "signed").id == cancellation.id
        cancelled = next(row for row in ObjectivePage.model_validate(objectives.list_records(db, institute, employee)).rows if row.objective.id == original.id)
        assert cancelled.period_state == "cancelled" and cancelled.value is None and cancelled.known_value is None and cancelled.source_count is None
        assert cancelled.objective.target == original.target and cancelled.objective.cancellation.id == cancellation.id
        with pytest.raises(HTTPException):
            objectives.create(db, institute, ObjectiveCreate.model_validate(payload(employee)), "changed-actor")
        db.rollback()


def test_objective_explicit_targets_pinned_calendar_and_recorded_progress(client, monkeypatch):
    institute, employee, service, _, _ = setup(client)
    exercise(main_module.engine, institute, employee, service, monkeypatch)


def test_objective_http_recovery_roles_limits_and_explicit_units(client):
    institute, employee, _, base, headers = setup(client)
    body = payload(employee)
    created = client.post(base+"/objectives", headers=headers, json=body)
    assert created.status_code == 200, created.text
    original = created.json()
    exact = {**body, "target": "90071992547409.93", "idempotency_key": "exact-target"}
    exact_reply = client.post(base+"/objectives", headers=headers, json=exact)
    assert exact_reply.status_code == 200, exact_reply.text
    assert exact_reply.json()["target"] == exact["target"]
    assert client.post(base+"/objectives", headers=headers, json=exact).json() == exact_reply.json()
    trailing = {**body, "target": "10.450000000000000000000000000000000000", "idempotency_key": "trailing"}
    assert client.post(base+"/objectives", headers=headers, json=trailing).json()["target"] == "10.45"
    assert client.post(base+"/objectives", headers=headers, json={**body, "target": trailing["target"]}).json() == original
    assert client.get(base+"/objectives/original/gross", headers=headers).json() == original
    assert client.get(base+"/objectives/original/missing", headers=headers).json() is None
    assert client.post(base+"/objectives", headers=headers, json={**body, "target": "99.00"}).status_code == 400
    for changes in [{"currency": None}, {"target": "0"}, {"target": "NaN"}, {"target": 10.45}, {"target": True}, {"last_day": "2026-10-24"},
        {"first_day": "2026-10-25T00:00:00Z"}, {"first_day": 0},
        {"metric": "completed_sessions", "currency": None, "target": "1.5"}, {"metric": "completed_sessions"}, {"actor_id": "forged"}]:
        assert client.post(base+"/objectives", headers=headers, json={**body, **changes}).status_code == 422
    for auth in [_auth_headers("accueil", institute), _auth_headers("responsable_institut", "foreign")]:
        assert client.post(base+"/objectives", headers=auth, json=body).status_code == 403
        assert client.get(f"{base}/employees/{employee}/objectives", headers=auth).status_code == 403
    assert client.get(f"{base}/employees/foreign/objectives", headers=headers).status_code == 404
    assert client.get(f"{base}/employees/{employee}/objectives?limit=51", headers=headers).status_code == 422
    assert client.get(f"{base}/employees/{employee}/objectives?limit=1&offset=0", headers=headers).json()["page"] == {"offset": 0, "limit": 1, "total": 3}
    cancel = {"reason": "Original correction", "idempotency_key": "cancel"}
    revoked = client.post(f"{base}/objectives/{original['id']}/cancel", headers=headers, json=cancel)
    assert revoked.status_code == 200
    assert client.get(base+"/objective-cancellations/original/cancel", headers=headers).json() == revoked.json()
    assert client.post(base+"/objectives", headers=headers, json={**body, "first_day": "9999-12-31", "last_day": "9999-12-31", "idempotency_key": "extreme"}).status_code == 400
    with Session(main_module.engine) as db:
        db.get(Institute, institute).timezone = "Pacific/Apia"
        db.commit()
    assert client.post(base+"/objectives", headers=headers, json={**body, "first_day": "2011-12-30", "last_day": "2011-12-30", "idempotency_key": "skipped"}).status_code == 400


def test_actual_postgres_objective_progress_and_same_key_race(postgres_flow, monkeypatch):
    engine, institute, employee, service = postgres_flow
    exercise(engine, institute, employee, service, monkeypatch)
    barrier = Barrier(2)
    def create():
        with Session(engine) as db:
            barrier.wait(timeout=10)
            return objectives.create(db, institute, ObjectiveCreate.model_validate({**payload(employee, "race"), "target": "90071992547409.93"}), "signed").id
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(create) for _ in range(2)]
        ids = [future.result(timeout=20) for future in futures]
    assert ids[0] == ids[1]
    with Session(engine) as db:
        assert len(list(db.scalars(select(EmployeeObjective)))) == 4
        original = db.scalar(select(EmployeeObjective).where(EmployeeObjective.id == ids[0]))
        assert ObjectiveRead.model_validate(original).target == Decimal("90071992547409.93")
        fields = {column.name: getattr(original, column.name) for column in EmployeeObjective.__table__.columns}
        for index, changes, constraint in [
            (0, {"institute_id": "foreign"}, "fk_objective_employee_owner"),
            (1, {"currency": None}, "ck_objective_metric_unit"),
            (2, {"metric": "completed_sessions", "currency": None, "target": "1.50"}, "ck_objective_metric_unit"),
            (3, {"target": "0.00"}, "ck_objective_period_target")]:
            db.add(EmployeeObjective(**{**fields, "id": f"invalid-{index}", "idempotency_key": f"invalid-{index}", **changes}))
            with pytest.raises(IntegrityError) as error:
                db.commit()
            assert error.value.orig.diag.constraint_name == constraint
            db.rollback()
        db.add(ObjectiveCancellation(id="foreign-cancel", institute_id="foreign", objective_id=ids[0], reason="Fixture",
                                    actor_id="signed", idempotency_key="foreign-cancel", created_at=utcnow()))
        with pytest.raises(IntegrityError) as error:
            db.commit()
        assert error.value.orig.diag.constraint_name == "fk_objective_cancel_owner"
        db.rollback()
        assert len(list(db.scalars(select(EmployeeObjective)))) == 4
        large_count = objectives.create(db, institute, ObjectiveCreate.model_validate({
            **payload(employee, "large-session-count"), "metric": "completed_sessions", "currency": None,
            "target": "999999999999999999"}), "signed")
        assert large_count.target == Decimal("999999999999999999")


def test_objective_page_batches_progress_without_per_objective_queries(client):
    institute, employee, _, _, _ = setup(client)
    with Session(main_module.engine) as db:
        for index in range(21):
            objectives.create(db, institute, ObjectiveCreate.model_validate(payload(employee, f"page-{index}")), "signed")
    statements = []
    def observe(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)
    event.listen(main_module.engine, "before_cursor_execute", observe)
    try:
        with Session(main_module.engine) as db:
            page = ObjectivePage.model_validate(objectives.list_records(db, institute, employee))
        assert page.page.total == 21 and len(page.rows) == 20
        assert len(statements) <= 7
        statements.clear()
        with Session(main_module.engine) as db:
            page = ObjectivePage.model_validate(objectives.list_records(db, institute, employee, offset=20))
        assert len(page.rows) == 1 and page.page.total == 21
        assert len(statements) <= 7
    finally:
        event.remove(main_module.engine, "before_cursor_execute", observe)
