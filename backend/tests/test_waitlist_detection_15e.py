from copy import deepcopy
from datetime import timedelta
import pytest
from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.waitlist import originals, lifecycle, sources, detection
from app.modules.waitlist.models import LifecycleOriginal
from app.modules.resources.models import ResourceReservation
from test_waitlist_sources_15d import prepare_sources
from test_waitlist_originals_15b import request
from test_waitlist_lifecycle_15c import transition
from test_waitlist_matching_15a import NOW
from test_workforce_absences_11b import setup
from test_ticket_workflow import _auth_headers
from test_postgres_scheduling_4d import postgres_flow


def exercise(engine, institute, employee, service, monkeypatch):
    root, activated = prepare_sources(engine, institute, employee, service, monkeypatch)
    monkeypatch.setattr(detection, "utcnow", lambda: NOW)
    # Detect any accidental per-row clock recapture, rather than merely checking
    # that a fixed monkeypatched clock happened to produce equal values.
    monkeypatch.setattr(sources, "utcnow", lambda: (_ for _ in ()).throw(AssertionError("Per-row recapture")))
    policy = sources.Policy(channel="email", history_requirement="review_only", permission_requirement="review_only")
    horizon = NOW+timedelta(hours=3)
    with Session(engine) as db:
        roots = [root]
        for n in range(25):
            target = originals.create(db, institute, request(service, employee, f"batch-demand-{n}"), "signed")
            roots.append(target)
            lifecycle.create(db, institute, transition(target, key=f"batch-activation-{n}"), "signed")
        cancelled = lifecycle.create(db, institute, transition(root, "cancel", activated, root, "batch-cancel"), "signed")
        first = detection.read(db, institute, horizon, policy)
        last = detection.read(db, institute, horizon, policy, 20)
        assert first.examined_roots == 26 and first.active == last.active == first.with_options == 25
        assert first.cancelled == 1 and first.without_options == 0 and first.unavailable_reasons == {}
        assert len(first.reviews) == 20 and len(last.reviews) == 5
        assert all(result.captured_at == result.review.capture.captured_at == NOW for result in first.reviews+last.reviews)
        assert len({result.state.root.original["id"] for result in first.reviews+last.reviews}) == 25
        assert first.allocation == "independent_alternatives_not_jointly_reserved"
        assert db.scalar(select(func.count()).select_from(ResourceReservation)) == 0
        grant_policy = sources.Policy(channel="email", history_requirement="review_only", permission_requirement="recorded_grant_required")
        refused = detection.read(db, institute, horizon, grant_policy, 20)
        assert refused.with_options == 0 and refused.without_options == 25
        assert refused.unavailable_reasons == {"permission_requirement_unmet": 25}
        # Corrupt a root outside the first page; bounded output must not weaken
        # the lifecycle/source verification cohort.
        victim = db.scalar(select(LifecycleOriginal).where(LifecycleOriginal.root_id == last.reviews[-1].state.root.original["id"]))
        before, before_hash = deepcopy(victim.original), victim.fingerprint
        raw = deepcopy(before); raw["activation_source"]["duration_minutes"] = 31
        victim.original = raw; victim.fingerprint = originals.fingerprint(raw); db.commit()
        with pytest.raises(HTTPException): detection.read(db, institute, horizon, policy, 0, 1)
        db.rollback(); victim.original = before; victim.fingerprint = before_hash; db.commit()
        for offset, limit in ((True, 20), (-1, 20), (0, 51)):
            with pytest.raises(HTTPException): detection.read(db, institute, horizon, policy, offset, limit)
        return first


def test_sqlite_whole_detection_and_signed_scope(client, monkeypatch):
    institute, employee, service, _, _ = setup(client)
    exercise(main_module.engine, institute, employee, service, monkeypatch)
    path = f"/api/v1/waitlist/institutes/{institute}/detection"
    params = dict(horizon_end=(NOW+timedelta(hours=3)).isoformat(), channel="email", history_requirement="review_only", permission_requirement="review_only")
    headers = _auth_headers("responsable_institut", institute)
    response = client.get(path, headers=headers, params=params)
    assert response.status_code == 200, response.text
    assert response.json()["active"] == 25 and len(response.json()["reviews"]) == 20
    for role, owner in (("accueil", institute), ("collaboratrice", institute), ("responsable_institut", "foreign")):
        assert client.get(path, params=params, headers=_auth_headers(role, owner)).status_code == 403
    assert client.get(path, params=params).status_code == 403
    assert client.post(path, headers=headers, json=params).status_code == 405
    assert client.get(path, headers=headers, params={**params, "horizon_end": "2026-10-09"}).status_code == 422


def test_actual_postgres_whole_detection(postgres_flow, monkeypatch):
    exercise(*postgres_flow, monkeypatch)
