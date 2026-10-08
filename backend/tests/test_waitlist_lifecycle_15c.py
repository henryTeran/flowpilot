from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
from threading import Barrier
import pytest
from fastapi import HTTPException
from sqlalchemy import select, func, event
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.waitlist import originals, lifecycle
from app.modules.waitlist.models import LifecycleOriginal
from app.modules.services.models import Service
from test_waitlist_originals_15b import prepare, request
from test_waitlist_matching_15a import NOW
from test_workforce_absences_11b import setup
from test_ticket_workflow import _auth_headers
from test_postgres_scheduling_4d import postgres_flow


def transition(root, action="activate", previous=None, target=None, key="activate-one"):
    target = target or root
    return lifecycle.Request(root_id=root.original["id"], root_fingerprint=root.fingerprint,
        previous_id=previous.original["id"] if previous else None,
        previous_fingerprint=previous.fingerprint if previous else None,
        action=action, target_id=target.original["id"], target_fingerprint=target.fingerprint,
        reason="Modification explicite de la demande", idempotency_key=key)


def exercise(engine, institute, employee, service, monkeypatch):
    prepare(engine, institute, service)
    monkeypatch.setattr(originals, "utcnow", lambda: NOW)
    monkeypatch.setattr(lifecycle, "utcnow", lambda: NOW)
    with Session(engine) as db:
        root = originals.create(db, institute, request(service, employee), "signed")
        assert lifecycle.audit(db, institute).total == 0
        activated = lifecycle.create(db, institute, transition(root), "signed")
        assert lifecycle.create(db, institute, transition(root), "signed") == activated
        assert lifecycle.audit(db, institute).active == 1
        replacement = originals.create(db, institute, request(service, employee, "new-demand").model_copy(
            update={"availability_evidence": "Nouvelle disponibilité déclarée"}), "signed")
        revised = lifecycle.create(db, institute, transition(root, "revise", activated, replacement, "revise-one"), "signed")
        with pytest.raises(HTTPException):
            lifecycle.create(db, institute, transition(root, "cancel", activated, root, "stale-cancel"), "signed")
        state = lifecycle.audit(db, institute).states[0]
        assert state.current_demand == replacement and len(state.events) == 2
        # Source disappearance/expiry cannot prevent cancellation or old-key recovery.
        db.get(Service, service).status = "inactive"; db.commit()
        monkeypatch.setattr(lifecycle, "utcnow", lambda: NOW+timedelta(days=10))
        cancelled = lifecycle.create(db, institute, transition(root, "cancel", revised, replacement, "cancel-one"), "signed")
        assert lifecycle.by_key(db, institute, "activate-one") == activated
        assert lifecycle.create(db, institute, transition(root), "signed") == activated
        final = lifecycle.audit(db, institute)
        assert final.active == 0 and final.cancelled == 1 and len(final.states[0].events) == 3
        assert final.states[0].state == "cancelled" and final.states[0].root == root
        with pytest.raises(HTTPException):
            lifecycle.create(db, institute, transition(root, "revise", cancelled, root, "resurrection"), "signed")
        with pytest.raises(HTTPException): lifecycle.create(db, institute, transition(root), "other-actor")
        assert db.scalar(select(func.count()).select_from(LifecycleOriginal)) == 3
        return root, activated


def test_sqlite_lifecycle_and_signed_scope(client, monkeypatch):
    institute, employee, service, _, _ = setup(client)
    root, activated = exercise(main_module.engine, institute, employee, service, monkeypatch)
    base = f"/api/v1/waitlist/institutes/{institute}/lifecycle"
    headers = _auth_headers("responsable_institut", institute)
    assert client.get(base, headers=headers).json()["cancelled"] == 1
    assert client.get(base+"/original-by-key?key=activate-one", headers=headers).json() == activated.model_dump(mode="json")
    assert client.get(base+f"/originals/{activated.original['id']}", headers=headers).json() == activated.model_dump(mode="json")
    assert client.get(base+f"/states/{root.original['id']}", headers=headers).json()["state"] == "cancelled"
    assert client.get(base+"/states/absent", headers=headers).status_code == 404
    for role, owner in (("accueil", institute), ("collaboratrice", institute), ("responsable_institut", "foreign")):
        denied = _auth_headers(role, owner)
        assert client.get(base, headers=denied).status_code == 403
        assert client.get(base+"/original-by-key?key=activate-one", headers=denied).status_code == 403
        assert client.get(base+f"/originals/{activated.original['id']}", headers=denied).status_code == 403
        assert client.get(base+f"/states/{root.original['id']}", headers=denied).status_code == 403
        assert client.post(base+"/originals", headers=denied, json=transition(root).model_dump(mode="json")).status_code == 403
    assert client.get(base).status_code == 403
    assert client.get(base+"?offset=-1", headers=headers).status_code == 422
    assert client.post(base+"/originals", headers=headers, json={**transition(root).model_dump(mode="json"), "actor_id": "injected"}).status_code == 422


def test_actual_postgres_lifecycle(postgres_flow, monkeypatch):
    exercise(*postgres_flow, monkeypatch)


def test_actual_postgres_conflicting_successors_and_same_key(postgres_flow, monkeypatch):
    engine, institute, employee, service = postgres_flow
    prepare(engine, institute, service)
    monkeypatch.setattr(originals, "utcnow", lambda: NOW)
    monkeypatch.setattr(lifecycle, "utcnow", lambda: NOW)
    with Session(engine) as db:
        root = originals.create(db, institute, request(service, employee), "signed")
    def race(payloads):
        barrier = Barrier(2)
        def run(payload):
            with Session(engine) as db:
                barrier.wait(timeout=10)
                try: return lifecycle.create(db, institute, payload, "signed")
                except HTTPException: return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(run, payloads))
    receipts = race([transition(root), transition(root)])
    assert receipts[0] == receipts[1] and receipts[0] is not None
    previous = receipts[0]
    results = race([transition(root, "cancel", previous, root, "cancel-a"), transition(root, "cancel", previous, root, "cancel-b")])
    assert sum(result is not None for result in results) == 1
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(LifecycleOriginal)) == 2


def test_actual_postgres_rollback_lost_ack_and_rehashed_chain_tamper(postgres_flow, monkeypatch):
    engine, institute, employee, service = postgres_flow
    prepare(engine, institute, service)
    monkeypatch.setattr(originals, "utcnow", lambda: NOW)
    monkeypatch.setattr(lifecycle, "utcnow", lambda: NOW)
    with Session(engine) as db:
        root = originals.create(db, institute, request(service, employee), "signed")
        def fail_flush(session, context): raise RuntimeError("flush failed")
        event.listen(db, "after_flush", fail_flush)
        try:
            with pytest.raises(RuntimeError, match="flush failed"): lifecycle.create(db, institute, transition(root), "signed")
        finally: event.remove(db, "after_flush", fail_flush)
        assert lifecycle.audit(db, institute).total == 0
        commit = db.commit
        def lost_ack():
            commit(); raise RuntimeError("acknowledgement lost")
        monkeypatch.setattr(db, "commit", lost_ack)
        with pytest.raises(RuntimeError, match="acknowledgement lost"): lifecycle.create(db, institute, transition(root), "signed")
    with Session(engine) as db:
        activated = lifecycle.by_key(db, institute, "activate-one")
        assert lifecycle.create(db, institute, transition(root), "signed") == activated
        row = db.get(LifecycleOriginal, activated.original["id"])
        for attack in (lambda raw: raw.update(action="cancel"), lambda raw: raw.update(previous_id="orphan"),
                lambda raw: raw.update(target_fingerprint="0"*64), lambda raw: raw.update(effect="booked"),
                lambda raw: raw.update(created_at=(NOW+timedelta(days=1)).isoformat())):
            raw = deepcopy(activated.original); attack(raw)
            row.original = raw; row.fingerprint = originals.fingerprint(raw); db.commit()
            with pytest.raises(HTTPException): lifecycle.audit(db, institute)
            db.rollback()
            row.original = deepcopy(activated.original); row.fingerprint = activated.fingerprint; db.commit()


def test_current_sources_required_only_for_new_activation(client, monkeypatch):
    institute, employee, service, _, _ = setup(client)
    prepare(main_module.engine, institute, service)
    monkeypatch.setattr(originals, "utcnow", lambda: NOW)
    monkeypatch.setattr(lifecycle, "utcnow", lambda: NOW+timedelta(days=1))
    with Session(main_module.engine) as db:
        root = originals.create(db, institute, request(service, employee), "signed")
        with pytest.raises(HTTPException): lifecycle.create(db, institute, transition(root), "signed")
        assert lifecycle.audit(db, institute).total == 0


def test_signed_activation_write_and_verified_cohort_pages(client, monkeypatch):
    institute, employee, service, _, _ = setup(client)
    prepare(main_module.engine, institute, service)
    monkeypatch.setattr(originals, "utcnow", lambda: NOW)
    monkeypatch.setattr(lifecycle, "utcnow", lambda: NOW)
    with Session(main_module.engine) as db:
        roots = [originals.create(db, institute, request(service, employee, f"root-{n}"), "signed") for n in range(25)]
    base = f"/api/v1/waitlist/institutes/{institute}/lifecycle"
    headers = _auth_headers("responsable_institut", institute)
    for n, root in enumerate(roots):
        response = client.post(base+"/originals", headers=headers, json=transition(root, key=f"activation-{n}").model_dump(mode="json"))
        assert response.status_code == 200, response.text
        assert response.json()["original"]["actor_id"] == "test-user"
    first = client.get(base, headers=headers).json()
    last = client.get(base+"?offset=20", headers=headers).json()
    assert first["total"] == last["total"] == first["active"] == 25
    assert len(first["states"]) == 20 and len(last["states"]) == 5
    victim_root = last["states"][-1]["root"]["original"]["id"]
    with Session(main_module.engine) as db:
        row = db.scalar(select(LifecycleOriginal).where(LifecycleOriginal.root_id == victim_root))
        raw = deepcopy(row.original); raw["activation_source"]["duration_minutes"] = 31
        row.original = raw; row.fingerprint = originals.fingerprint(raw); db.commit()
    assert client.get(base+"?limit=1", headers=headers).status_code == 400
