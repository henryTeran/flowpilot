from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from threading import Barrier
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.modules.workforce import work_intervals
from app.modules.workforce.work_interval_schemas import WorkIntervalCreate, WorkIntervalPage
from app.modules.workforce.absence_schemas import AbsenceCancel
from app.modules.workforce.models import EmployeeWorkInterval, WorkIntervalCancellation
from test_workforce_absences_11b import setup
from test_ticket_workflow import _auth_headers
from test_postgres_scheduling_4d import postgres_flow


def payload(employee, key="original"):
    return dict(employee_id=employee, start_time="2025-10-26T02:30:00+02:00", end_time="2025-10-26T02:30:00+01:00",
                reason="Declared effective work excluding breaks", idempotency_key=key)


def test_signed_effective_hours_original_recovery_overlap_cancellation_and_limits(client):
    institute, employee, _, _, _ = setup(client)
    headers = _auth_headers("responsable_institut", institute)
    base = f"/api/v1/workforce/institutes/{institute}"
    body = payload(employee)
    original_reply = client.post(base+"/work-intervals", headers=headers, json=body)
    assert original_reply.status_code == 200, original_reply.text
    original = original_reply.json()
    assert datetime.fromisoformat(original["end_time"])-datetime.fromisoformat(original["start_time"]) == timedelta(hours=1)
    assert client.post(base+"/work-intervals", headers=headers, json=body).json() == original
    assert client.get(base+"/work-intervals/original/original", headers=headers).json() == original
    assert client.get(base+"/work-intervals/original/missing", headers=headers).json() is None
    assert client.post(base+"/work-intervals", headers=headers, json={**body, "reason": "Changed"}).status_code == 400
    assert client.post(base+"/work-intervals", headers=headers, json={**body, "idempotency_key": "overlap"}).status_code == 400
    adjacent = {**body, "start_time": "2025-10-26T01:30:00Z", "end_time": "2025-10-26T02:30:00Z", "idempotency_key": "adjacent"}
    assert client.post(base+"/work-intervals", headers=headers, json=adjacent).status_code == 200
    assert client.post(base+"/work-intervals", headers=headers, json={**body, "end_time": "9998-01-01T00:00:00Z", "idempotency_key": "future"}).status_code == 400
    for changes in [{"start_time": "2025-10-26T00:30:00"}, {"end_time": body["start_time"]}, {"actor_id": "forged"},
                    {"start_time": "0001-01-01T00:00:00+14:00"}, {"start_time": 0}, {"end_time": True}]:
        assert client.post(base+"/work-intervals", headers=headers, json={**body, **changes}).status_code == 422
    for role, scope in [("accueil", institute), ("responsable_institut", "foreign")]:
        other = _auth_headers(role, scope)
        assert client.post(base+"/work-intervals", headers=other, json=body).status_code == 403
        assert client.get(base+f"/employees/{employee}/work-intervals", headers=other).status_code == 403
        assert client.get(base+"/work-intervals/original/original", headers=other).status_code == 403
    assert client.get(base+"/employees/foreign/work-intervals", headers=headers).status_code == 404
    assert client.get(base+f"/employees/{employee}/work-intervals?limit=51", headers=headers).status_code == 422
    page = WorkIntervalPage.model_validate(client.get(base+f"/employees/{employee}/work-intervals?limit=1", headers=headers).json())
    assert page.page.total == 2 and len(page.rows) == 1
    cancel = dict(reason="Corrected declaration", idempotency_key="cancel")
    cancellation = client.post(base+f"/work-intervals/{original['id']}/cancel", headers=headers, json=cancel)
    assert cancellation.status_code == 200
    assert client.post(base+f"/work-intervals/{original['id']}/cancel", headers=headers, json=cancel).json() == cancellation.json()
    assert client.get(base+"/work-interval-cancellations/original/cancel", headers=headers).json() == cancellation.json()
    assert client.post(base+f"/work-intervals/{original['id']}/cancel", headers=headers, json={**cancel, "idempotency_key": "second"}).status_code == 400
    recovered = client.get(base+f"/work-intervals/{original['id']}", headers=headers).json()
    assert {k: v for k, v in recovered.items() if k != "cancellation"} == {k: v for k, v in original.items() if k != "cancellation"}
    assert client.post(base+"/work-intervals", headers=headers, json={**body, "idempotency_key": "corrected"}).status_code == 200


def test_actual_postgres_hours_lock_serializes_overlap_and_original_replay(postgres_flow, monkeypatch):
    engine, institute, employee, _ = postgres_flow
    barrier = Barrier(2)
    def create(key):
        with Session(engine) as db:
            barrier.wait(timeout=10)
            try:
                return work_intervals.create(db, institute, WorkIntervalCreate.model_validate(payload(employee, key)), "signed").id
            except HTTPException as error:
                db.rollback(); return error.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(create, key) for key in ("left", "right")]
        values = [f.result(timeout=20) for f in futures]
    assert sum(v == 400 for v in values) == 1
    with Session(engine) as db:
        row = db.scalar(select(EmployeeWorkInterval))
        body = WorkIntervalCreate.model_validate(payload(employee, row.idempotency_key))
        monkeypatch.setattr(work_intervals, "utcnow", lambda: datetime(2020, 1, 1, tzinfo=timezone.utc))
        assert work_intervals.create(db, institute, body, "signed").id == row.id
        with pytest.raises(HTTPException):
            work_intervals.create(db, institute, body, "other-actor")
        db.rollback()
        assert WorkIntervalPage.model_validate(work_intervals.list_records(db, institute, employee)).page.total == 1
        monkeypatch.setattr(work_intervals, "utcnow", lambda: datetime(2026, 10, 1, tzinfo=timezone.utc))
        work_intervals.cancel(db, institute, row.id, AbsenceCancel(reason="Corrected", idempotency_key="cancel"), "signed")
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(create, "same") for _ in range(2)]
        values = [f.result(timeout=20) for f in futures]
    assert values[0] == values[1] and isinstance(values[0], str)
    with Session(engine) as db:
        row = db.get(EmployeeWorkInterval, values[0])
        fields = {column.name: getattr(row, column.name) for column in EmployeeWorkInterval.__table__.columns}
        for changes, constraint in [({"institute_id": "foreign"}, "fk_work_interval_employee_owner"),
                                    ({"end_time": row.start_time}, "ck_work_interval_positive")]:
            db.add(EmployeeWorkInterval(**{**fields, "id": "invalid", "idempotency_key": "invalid", **changes}))
            with pytest.raises(IntegrityError) as error:
                db.commit()
            assert error.value.orig.diag.constraint_name == constraint
            db.rollback()
        assert len(list(db.scalars(select(EmployeeWorkInterval)))) == 2
        db.add(WorkIntervalCancellation(id="foreign-cancel", institute_id="foreign", work_interval_id=values[0],
            reason="Fixture", actor_id="signed", idempotency_key="foreign-cancel", created_at=datetime(2026, 10, 1, tzinfo=timezone.utc)))
        with pytest.raises(IntegrityError) as error:
            db.commit()
        assert error.value.orig.diag.constraint_name == "fk_work_interval_cancel_owner"
        db.rollback()
