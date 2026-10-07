from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.crm import policies
from test_crm_segments_12c import policy
from test_crm_metrics_12a import NOW
from test_postgres_scheduling_4d import postgres_flow
from test_ticket_workflow import _auth_headers, _bootstrap_reference_data


def body(institute, key="original", previous=None, **changes):
    return policies.PolicyCreate(policy=policy(institute_id=institute, **changes),
        previous_policy_id=previous, reason="Explicit fixture policy", idempotency_key=key)


def exercise(engine, institute, monkeypatch):
    monkeypatch.setattr(policies, "utcnow", lambda: NOW)
    with Session(engine) as db:
        assert policies.current(db, institute) is None
        first = policies.create(db, institute, body(institute), "test-user")
        second = policies.create(db, institute, body(institute, "correction", first.id, vip_gross_minor="500"), "test-user")
        assert policies.current(db, institute) == second
        assert policies.require(db, institute, first.id) == first
        assert policies.original(db, institute, "missing") is None
        monkeypatch.setattr(policies, "utcnow", lambda: NOW-timedelta(days=1))
        assert policies.create(db, institute, body(institute), "test-user") == first
        for payload, actor in ((body(institute), "different"),
            (body(institute, vip_gross_minor="700"), "test-user"),
            (body(institute, "stale", first.id), "test-user"),
            (body(institute, "badclock", second.id), "test-user"),
            (body(institute, "unsigned", second.id), None),
            (body("foreign", "foreign", second.id), "test-user")):
            with pytest.raises(HTTPException) as error:
                policies.create(db, institute, payload, actor)
            assert error.value.status_code == 400
        assert policies.current(db, institute) == second
        assert policies.original(db, "foreign", "original") is None
        with pytest.raises(HTTPException) as error:
            policies.require(db, "foreign", first.id)
        assert error.value.status_code == 404


def test_sqlite_original_correction_replay_clock_and_http_scope(client, monkeypatch):
    institute, _, _ = _bootstrap_reference_data(client)
    exercise(main_module.engine, institute, monkeypatch)
    path = f"/api/v1/crm/institutes/{institute}/segment-policies"
    headers = _auth_headers("responsable_institut", institute)
    first = client.get(path+"/original/original", headers=headers).json()
    assert client.post(path, headers=headers, json=body(institute).model_dump()).json() == first
    assert client.get(path+"/"+first["id"], headers=headers).json() == first
    assert client.get(path+"/current", headers=headers).json()["previous_policy_id"] == first["id"]
    for role, tenant in (("accueil", institute), ("collaboratrice", institute),
        ("responsable_institut", "foreign"), ("responsable_institut", None)):
        auth = _auth_headers(role, tenant)
        assert client.post(path, headers=auth, json=body(institute).model_dump()).status_code == 403
        assert client.get(path+"/current", headers=auth).status_code == 403
    assert client.get(path+"/current").status_code == 403
    assert client.post(path, headers=headers, json={**body(institute).model_dump(), "actor_id": "spoof"}).status_code == 422


def test_postgres_original_correction_replay(postgres_flow, monkeypatch):
    engine, institute, _, _ = postgres_flow
    exercise(engine, institute, monkeypatch)


def test_postgres_concurrent_corrections_require_the_same_explicit_predecessor(postgres_flow, monkeypatch):
    engine, institute, _, _ = postgres_flow
    monkeypatch.setattr(policies, "utcnow", lambda: NOW)
    with Session(engine) as db:
        first = policies.create(db, institute, body(institute), "manager")
    barrier = Barrier(2)
    def write(key):
        with Session(engine) as db:
            barrier.wait(timeout=10)
            try:
                return policies.create(db, institute, body(institute, key, first.id), "manager").id
            except HTTPException as error:
                assert error.status_code == 400
                return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(write, ("a", "b")))
    assert sum(value is not None for value in results) == 1
    with Session(engine) as db:
        assert policies.current(db, institute).id in results
        assert policies.require(db, institute, first.id) == first
