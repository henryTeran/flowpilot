from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
from threading import Barrier
import pytest
from fastapi import HTTPException
from sqlalchemy import select, func, event
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.optimizer import originals, policy, domain
from app.modules.optimizer.models import PolicyOriginal
from app.modules.institutes.models import Institute
from test_optimizer_policy_16b import rule
from test_waitlist_matching_15a import NOW
from test_workforce_absences_11b import setup
from test_ticket_workflow import _auth_headers
from test_postgres_scheduling_4d import postgres_flow


def request(key="optimizer-one"):
    return originals.Request(terms=policy.Terms(rules=[rule(f, enabled=f == "utilization_score") for f in domain.FACTORS]),
        reason="Explicit scoring assumptions reviewed\nwith manager", idempotency_key=key)


def exercise(engine, institute, monkeypatch):
    monkeypatch.setattr(originals, "utcnow", lambda: NOW)
    with Session(engine) as db:
        receipt = originals.create(db, institute, request(), "signed-manager")
        assert receipt.original["actor_id"] == "signed-manager"
        assert receipt.original["action"] == "scoring_assumptions_only_no_booking_or_contact"
        assert originals.fingerprint(receipt.original) == receipt.fingerprint
        for n in range(24): originals.create(db, institute, request(f"optimizer-{n}"), "signed-manager")
        assert originals.audit(db, institute).total == 25
        assert len(originals.audit(db, institute).originals) == 20
        assert len(originals.audit(db, institute, 20).originals) == 5
        assert originals.by_key(db, institute, "absent") is None
        assert originals.require(db, institute, receipt.original["id"]) == receipt
        assert originals.create(db, institute, request(), "signed-manager") == receipt
        for body, actor in [(request(), "other"), (request().model_copy(update={"reason": "Different assumption"}), "signed-manager")]:
            with pytest.raises(HTTPException): originals.create(db, institute, body, actor)
        victim = db.scalar(select(PolicyOriginal).order_by(PolicyOriginal.created_at.desc(), PolicyOriginal.id.desc()).limit(1))
        raw, digest = deepcopy(victim.original), victim.fingerprint
        altered = deepcopy(raw); altered["action"] = "book_now"
        victim.original = altered; victim.fingerprint = originals.fingerprint(altered); db.commit()
        with pytest.raises(HTTPException): originals.audit(db, institute, 0, 1)
        db.rollback(); victim.original = raw; victim.fingerprint = digest; db.commit()
    monkeypatch.setattr(originals, "utcnow", lambda: NOW+timedelta(days=100))
    with Session(engine) as db:
        assert originals.create(db, institute, request(), "signed-manager") == receipt
        assert originals.by_key(db, institute, "optimizer-one") == receipt
    return receipt


def test_sqlite_retention_and_signed_role_scope(client, monkeypatch):
    institute, *_ = setup(client)
    receipt = exercise(main_module.engine, institute, monkeypatch)
    base = f"/api/v1/optimizer/institutes/{institute}"
    headers = _auth_headers("responsable_institut", institute)
    assert client.get(base+"/policy-originals", headers=headers).json()["total"] == 25
    for role, owner in [("accueil", institute), ("collaboratrice", institute), ("responsable_institut", "foreign")]:
        denied = _auth_headers(role, owner)
        for suffix in ["/policy-originals", "/policy-original-by-key?key=optimizer-one", f"/policy-originals/{receipt.original['id']}"]:
            assert client.get(base+suffix, headers=denied).status_code == 403
        assert client.post(base+"/policy-originals", headers=denied, json=request("denied").model_dump(mode="json")).status_code == 403
    with Session(main_module.engine) as db:
        owner = db.get(Institute, institute)
        db.add(Institute(id="foreign", name="Other institute", region_id=owner.region_id, city=owner.city, timezone="Europe/Zurich")); db.commit()
        assert originals.by_key(db, "foreign", "optimizer-one") is None
        with pytest.raises(HTTPException) as error: originals.require(db, "foreign", receipt.original["id"])
        assert error.value.status_code == 404


def test_signed_write_replay_exact_body_actor_and_independent_receipt_reads(client, monkeypatch):
    institute, *_ = setup(client); monkeypatch.setattr(originals, "utcnow", lambda: NOW)
    base = f"/api/v1/optimizer/institutes/{institute}"
    headers = _auth_headers("responsable_institut", institute); body = request().model_dump(mode="json")
    response = client.post(base+"/policy-originals", headers=headers, json=body)
    assert response.status_code == 200, response.text
    receipt = response.json(); assert receipt["original"]["actor_id"] == "test-user"
    assert client.post(base+"/policy-originals", headers=headers, json=body).json() == receipt
    assert client.get(base+"/policy-original-by-key", params={"key": "optimizer-one"}, headers=headers).json() == receipt
    assert client.get(base+f"/policy-originals/{receipt['original']['id']}", headers=headers).json() == receipt
    for field in ["actor_id", "institute_id", "created_at", "score"]:
        assert client.post(base+"/policy-originals", headers=headers, json={**body, field: "injected"}).status_code == 422
    body["terms"]["rules"][0]["ceiling"] = "100"
    assert client.post(base+"/policy-originals", headers=headers, json=body).status_code == 422


def test_actual_postgres_retention_paging_and_rehashed_off_page_tamper(postgres_flow, monkeypatch):
    engine, institute, *_ = postgres_flow
    exercise(engine, institute, monkeypatch)


@pytest.mark.parametrize("conflicting", [False, True])
def test_actual_postgres_same_key_and_conflicting_assumptions(postgres_flow, monkeypatch, conflicting):
    engine, institute, *_ = postgres_flow; monkeypatch.setattr(originals, "utcnow", lambda: NOW)
    barrier = Barrier(2)
    def run(n):
        with Session(engine) as db:
            body = request().model_copy(update={"reason": "Other explicit assumption"}) if n and conflicting else request()
            barrier.wait(timeout=10)
            try: return originals.create(db, institute, body, "signed")
            except HTTPException as error: return error.status_code
    with ThreadPoolExecutor(max_workers=2) as pool: results = list(pool.map(run, range(2)))
    if conflicting: assert sum(isinstance(r, int) and r == 400 for r in results) == 1
    else: assert results[0] == results[1]
    with Session(engine) as db: assert db.scalar(select(func.count()).select_from(PolicyOriginal)) == 1


def test_actual_postgres_rollback_and_committed_lost_ack(postgres_flow, monkeypatch):
    engine, institute, *_ = postgres_flow; monkeypatch.setattr(originals, "utcnow", lambda: NOW)
    with Session(engine) as db:
        def fail(session, context): raise RuntimeError("forced flush failure")
        event.listen(db, "after_flush", fail)
        try:
            with pytest.raises(RuntimeError, match="forced flush"): originals.create(db, institute, request(), "signed")
        finally: event.remove(db, "after_flush", fail)
        assert db.scalar(select(func.count()).select_from(PolicyOriginal)) == 0
        commit = db.commit
        def lost_ack(): commit(); raise RuntimeError("committed acknowledgement lost")
        monkeypatch.setattr(db, "commit", lost_ack)
        with pytest.raises(RuntimeError, match="acknowledgement lost"): originals.create(db, institute, request(), "signed")
    with Session(engine) as db:
        receipt = originals.by_key(db, institute, "optimizer-one")
        assert receipt is not None and originals.create(db, institute, request(), "signed") == receipt
        assert db.scalar(select(func.count()).select_from(PolicyOriginal)) == 1


def test_raw_rehashed_columns_future_and_normalization_tamper_refuse(client, monkeypatch):
    institute, *_ = setup(client); monkeypatch.setattr(originals, "utcnow", lambda: NOW)
    with Session(main_module.engine) as db:
        receipt = originals.create(db, institute, request(), "signed")
        row = db.get(PolicyOriginal, receipt.original["id"])
        for attack in [lambda raw: raw.update(actor_id="other"), lambda raw: raw.update(created_at=(NOW+timedelta(microseconds=1)).isoformat()),
                lambda raw: raw["terms"]["rules"][0].update(ceiling="100"), lambda raw: raw.update(institute_id="foreign"),
                lambda raw: raw.update(reason=raw["reason"]+" "), lambda raw: raw["terms"]["rules"][0].update(reason="  Noncanonical evidence ")]:
            raw = deepcopy(receipt.original); attack(raw); row.original = raw; row.fingerprint = originals.fingerprint(raw); db.commit()
            with pytest.raises(HTTPException): originals.by_key(db, institute, "optimizer-one")
            db.rollback()
        row.original = deepcopy(receipt.original); row.fingerprint = "0"*64; db.commit()
        with pytest.raises(HTTPException): originals.require(db, institute, row.id)
