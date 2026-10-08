from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from fastapi import HTTPException
from sqlalchemy import select, func, event
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.base import plans, read_capabilities as base
from app.modules.base.models import PlanOriginal
from app.modules.waitlist.models import DemandOriginal, LifecycleOriginal
from app.modules.optimizer.models import PolicyOriginal
from test_base_routes_17b import prepared
from test_optimizer_sources_16d import prepare
from test_ticket_workflow import _auth_headers
from test_waitlist_matching_15a import NOW
from test_postgres_scheduling_4d import postgres_flow


def request(invocation, key="plan-one", utterance="Lire la liste d'attente"):
    return plans.Request(intent={"utterance": utterance, "selections": [invocation]}, reason="Explicit preparation reviewed", idempotency_key=key)


def exercise(engine, institute, invocation, monkeypatch):
    monkeypatch.setattr(plans, "utcnow", lambda: NOW)
    monkeypatch.setattr(base, "utcnow", lambda: NOW)
    principal = base.Principal(actor_id="signed-manager", institute_id=institute, role="responsable_institut")
    with Session(engine) as db:
        models = (DemandOriginal, LifecycleOriginal, PolicyOriginal)
        counts = tuple(db.scalar(select(func.count()).select_from(m)) for m in models)
        receipt = plans.create(db, principal, institute, request(invocation))
        assert receipt.fingerprint == plans.fingerprint(receipt.original)
        original = plans.Original.model_validate(receipt.original)
        assert original.evidence.result.state == "active"
        assert original.resolution.invocation.model_dump(mode="json") == invocation
        assert original.actor_id == principal.actor_id
        assert original.effect == "retained_read_suggest_preparation_not_approval_or_execution"
        original_invoke = base.invoke
        def no_recapture(*args): raise AssertionError("Replay must retain the original capture")
        monkeypatch.setattr(base, "invoke", no_recapture)
        assert plans.create(db, principal, institute, request(invocation)) == receipt
        assert plans.by_key(db, principal, institute, "plan-one") == receipt
        assert plans.by_key(db, principal, institute, "absent") is None
        assert plans.require(db, principal, institute, original.id) == receipt
        for changed, actor in [(request(invocation).model_copy(update={"reason": "Changed reason"}), principal), (request(invocation), principal.model_copy(update={"actor_id": "other"}))]:
            with pytest.raises(HTTPException): plans.create(db, actor, institute, changed)
        monkeypatch.setattr(base, "invoke", original_invoke)
        for n in range(24): plans.create(db, principal, institute, request(invocation, f"plan-{n}"))
        assert plans.audit(db, principal, institute).total == 25
        assert len(plans.audit(db, principal, institute).originals) == 20
        assert len(plans.audit(db, principal, institute, 20).originals) == 5
        assert plans.audit(db, principal, institute, 25).originals == ()
        assert tuple(db.scalar(select(func.count()).select_from(m)) for m in models) == counts
        row = db.get(PlanOriginal, original.id)
        raw = deepcopy(row.original)
        for target, field in [("resolution", "selected_root"), ("evidence", "nested_root")]:
            bad = deepcopy(raw)
            if target == "resolution": bad["resolution"]["invocation"]["arguments"]["root_id"] = "invented"
            else: bad["evidence"]["result"]["root"]["original"]["reason"] = "Changed nested evidence"
            row.original = bad; row.fingerprint = plans.fingerprint(bad); db.commit()
            # Full cohort verification refuses corrupt history even outside the page.
            with pytest.raises(HTTPException): plans.audit(db, principal, institute, 100)
            db.rollback()
            row = db.get(PlanOriginal, original.id)
        row = db.get(PlanOriginal, original.id); row.original = raw; row.fingerprint = plans.fingerprint(raw); db.commit()
        assert plans.audit(db, principal, institute).total == 25
    return receipt


def test_sqlite_plan_originals_replay_audit_tamper_and_signed_routes(client, monkeypatch):
    institute, path, invocations = prepared(client, monkeypatch)
    receipt = exercise(main_module.engine, institute, invocations[0], monkeypatch)
    headers = _auth_headers("responsable_institut", institute)
    response = client.post(path+"/plans", json=request(invocations[0], "http-plan").model_dump(mode="json"), headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["original"]["actor_id"] == "test-user"
    assert client.get(path+"/plan-by-key?key=http-plan", headers=headers).json() == response.json()
    assert client.get(path+"/plans/"+receipt.original["id"], headers=headers).json() == receipt.model_dump(mode="json")
    for role, owner in [("accueil", institute), ("collaboratrice", institute), ("direction", institute), ("super_admin", institute), ("responsable_institut", "foreign")]:
        denied = _auth_headers(role, owner)
        for suffix in ("/plans", "/plan-by-key?key=plan-one", "/plans/"+receipt.original["id"]):
            assert client.get(path+suffix, headers=denied).status_code == 403
        assert client.post(path+"/plans", json=request(invocations[0], "denied").model_dump(mode="json"), headers=denied).status_code == 403
    body = request(invocations[0], "injected").model_dump(mode="json")
    for field in ("actor_id", "resolution", "evidence", "approved", "sql", "created_at"):
        assert client.post(path+"/plans", json={**body, field: "injected"}, headers=headers).status_code == 422
    ambiguous = {**body, "intent": {"utterance": "Autre chose", "selections": [invocations[0]]}}
    assert client.post(path+"/plans", json=ambiguous, headers=headers).status_code == 400
    with Session(main_module.engine) as db:
        assert db.scalar(select(func.count()).select_from(PlanOriginal)) == 26


def test_actual_postgres_plan_retention_and_history(postgres_flow, monkeypatch):
    engine, institute, employee, service = postgres_flow
    selected = prepare(engine, institute, employee, service, monkeypatch)
    exercise(engine, institute, {"capability": "WAITLIST_READ", "arguments": {"root_id": selected.root_id}}, monkeypatch)


@pytest.mark.parametrize("conflicting", [False, True])
def test_actual_postgres_plan_key_races_bind_request(postgres_flow, monkeypatch, conflicting):
    engine, institute, employee, service = postgres_flow
    selected = prepare(engine, institute, employee, service, monkeypatch)
    monkeypatch.setattr(plans, "utcnow", lambda: NOW); monkeypatch.setattr(base, "utcnow", lambda: NOW)
    principal = base.Principal(actor_id="signed", institute_id=institute, role="responsable_institut")
    body = request({"capability": "WAITLIST_READ", "arguments": {"root_id": selected.root_id}})
    barrier = Barrier(2)
    def run(n):
        with Session(engine) as db:
            terms = body.model_copy(update={"reason": "Other explicit request"}) if n and conflicting else body
            barrier.wait(timeout=10)
            try: return plans.create(db, principal, institute, terms)
            except HTTPException as error: return error.status_code
    with ThreadPoolExecutor(max_workers=2) as pool: results = list(pool.map(run, range(2)))
    if conflicting: assert sum(isinstance(r, int) and r == 400 for r in results) == 1
    else: assert results[0] == results[1]
    with Session(engine) as db: assert db.scalar(select(func.count()).select_from(PlanOriginal)) == 1


def test_actual_postgres_plan_rollback_and_lost_ack_recovery(postgres_flow, monkeypatch):
    engine, institute, employee, service = postgres_flow
    selected = prepare(engine, institute, employee, service, monkeypatch)
    monkeypatch.setattr(plans, "utcnow", lambda: NOW); monkeypatch.setattr(base, "utcnow", lambda: NOW)
    principal = base.Principal(actor_id="signed", institute_id=institute, role="responsable_institut")
    body = request({"capability": "WAITLIST_READ", "arguments": {"root_id": selected.root_id}})
    with Session(engine) as db:
        def fail(*args): raise RuntimeError("forced plan flush failure")
        event.listen(db, "after_flush", fail)
        try:
            with pytest.raises(RuntimeError, match="forced plan flush"): plans.create(db, principal, institute, body)
        finally: event.remove(db, "after_flush", fail)
        assert db.scalar(select(func.count()).select_from(PlanOriginal)) == 0
        commit = db.commit
        def lost_ack(): commit(); raise RuntimeError("committed plan acknowledgement lost")
        monkeypatch.setattr(db, "commit", lost_ack)
        with pytest.raises(RuntimeError, match="acknowledgement lost"): plans.create(db, principal, institute, body)
    with Session(engine) as db:
        receipt = plans.by_key(db, principal, institute, body.idempotency_key)
        assert receipt is not None and plans.create(db, principal, institute, body) == receipt
        assert db.scalar(select(func.count()).select_from(PlanOriginal)) == 1


def test_current_matching_and_scoring_preparations_preserve_refusal_and_stale_guards(client, monkeypatch):
    institute, path, invocations = prepared(client, monkeypatch)
    monkeypatch.setattr(plans, "utcnow", lambda: NOW)
    headers = _auth_headers("responsable_institut", institute)
    for n, utterance in [(1, "Trouver des créneaux pour la liste d'attente"), (2, "Optimiser le planning")]:
        body = request(invocations[n], f"plan-{n}", utterance).model_dump(mode="json")
        response = client.post(path+"/plans", json=body, headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["original"]["evidence"]["result"]["review"]["options"]
        stale = deepcopy(body); stale["idempotency_key"] += "-stale"; stale["intent"]["selections"][0]["arguments"]["expected_event_fingerprint"] = "0"*64
        assert client.post(path+"/plans", json=stale, headers=headers).status_code == 400
    refused = deepcopy(invocations[1]); refused["arguments"]["policy"]["permission_requirement"] = "recorded_grant_required"
    response = client.post(path+"/plans", json=request(refused, "refusal", "Trouver des créneaux pour la liste d'attente").model_dump(mode="json"), headers=headers)
    assert response.status_code == 200
    assert response.json()["original"]["evidence"]["result"]["unavailable_reason"] == "permission_requirement_unmet"
