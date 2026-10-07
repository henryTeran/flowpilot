from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier
from copy import deepcopy
import pytest
from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.revenue import scenario_originals as originals, sources
from app.modules.revenue.models import ScenarioOriginal
from app.modules.tickets.models import QueueTicket
from test_revenue_scenarios_14d import request
from test_revenue_sources_14a import exercise
from test_revenue_billing_14a import NOW
from test_ticket_workflow import _bootstrap_reference_data, _auth_headers
from test_postgres_scheduling_4d import postgres_flow


def declaration(key="scenario-one"):
    return originals.Declaration(assumptions=request(), reason="Explicit conditional gross scenario", idempotency_key=key)


def check(engine, institute, service, monkeypatch):
    exercise(engine, institute, service, monkeypatch)
    monkeypatch.setattr(originals, "utcnow", lambda: NOW)
    with Session(engine) as db:
        unavailable = originals.create(db, institute, declaration(), "signed-manager")
        assert unavailable.original["unavailable_reason"] == "undated_paid_tickets"
        assert unavailable.original["retained"] is True and unavailable.original["validated_prediction"] is False
        assert originals.fingerprint(unavailable.original) == unavailable.fingerprint
        db.delete(db.get(QueueTicket, "revenue-undated")); db.commit()
        valued = originals.create(db, institute, declaration("scenario-valued"), "signed-manager")
        assert valued.original["projected_gross_minor"] == dict(numerator="2525", denominator="2")
        db.get(QueueTicket, "revenue-00").total_amount = Decimal("2.01"); db.commit()
    old_read = sources.read
    monkeypatch.setattr(sources, "read", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Replay recaptured current sources")))
    monkeypatch.setattr(originals, "utcnow", lambda: NOW+timedelta(days=100))
    with Session(engine) as db:
        assert originals.create(db, institute, declaration("scenario-valued"), "signed-manager") == valued
        assert originals.by_key(db, institute, "scenario-valued") == valued
        assert originals.require(db, institute, valued.original["id"]) == valued
        assert originals.by_key(db, institute, "absent") is None
        for payload, actor in ((declaration("scenario-valued"), "other-actor"),
            (declaration("scenario-valued").model_copy(update={"reason": "Changed declaration"}), "signed-manager")):
            with pytest.raises(HTTPException): originals.create(db, institute, payload, actor)
        assert originals.create(db, institute, declaration(), "signed-manager") == unavailable
    monkeypatch.setattr(sources, "read", old_read); monkeypatch.setattr(originals, "utcnow", lambda: NOW)
    with Session(engine) as db:
        fresh = originals.create(db, institute, declaration("scenario-fresh"), "signed-manager")
        assert fresh.original["projected_gross_minor"] == dict(numerator="2625", denominator="2")
        assert valued.original["projected_gross_minor"]["numerator"] == "2525"
        for n in range(22): originals.create(db, institute, declaration(f"scenario-{n:02}"), "signed-manager")
        page = originals.audit(db, institute)
        assert page.total == 25 and len(page.originals) == 20 and page.full_original_cohort_verified
        final = originals.audit(db, institute, 20)
        assert final.total == 25 and len(final.originals) == 5
        victim = db.scalar(select(ScenarioOriginal).where(ScenarioOriginal.institute_id == institute)
            .order_by(ScenarioOriginal.created_at.desc(), ScenarioOriginal.id.desc()).limit(1))
        raw = dict(victim.original); raw["action_executed"] = True
        victim.original = raw; victim.fingerprint = originals.fingerprint(raw); db.commit()
        with pytest.raises(HTTPException): originals.audit(db, institute)  # Corrupt off-page frame refuses whole read.
        with pytest.raises(HTTPException): originals.by_key(db, institute, victim.idempotency_key)


def test_sqlite_original_evidence_replay_audit_and_signed_scope(client, monkeypatch):
    institute, _, services = _bootstrap_reference_data(client)
    check(main_module.engine, institute, services[0]["id"], monkeypatch)
    base = f"/api/v1/revenue/institutes/{institute}/scenarios"
    headers = _auth_headers("responsable_institut", institute)
    value = client.get(base+"/original-by-key", headers=headers, params={"key": "scenario-valued"})
    assert value.status_code == 200 and value.json()["original"]["actor_id"] == "signed-manager"
    new = client.post(base+"/originals", headers=headers, json=declaration("signed-api").model_dump(mode="json"))
    assert new.status_code == 200 and new.json()["original"]["actor_id"] == "test-user"
    identifier = new.json()["original"]["id"]
    assert client.get(base+f"/originals/{identifier}", headers=headers).json() == new.json()
    for role, owner in (("accueil", institute), ("collaboratrice", institute), ("responsable_institut", "foreign")):
        denied = _auth_headers(role, owner)
        for path in ("/originals", "/original-by-key?key=signed-api", f"/originals/{identifier}"):
            assert client.get(base+path, headers=denied).status_code == 403
        assert client.post(base+"/originals", headers=denied, json=declaration().model_dump(mode="json")).status_code == 403
    assert client.get(base+"/originals").status_code == 403
    assert client.post(base+"/originals", headers=headers, json={**declaration().model_dump(mode="json"), "actor_id": "injected"}).status_code == 422
    assert client.post(base+"/originals", headers=headers, json={**declaration().model_dump(mode="json"), "evidence": {}}).status_code == 422
    assert client.get(base+"/originals?offset=-1", headers=headers).status_code == 422
    assert client.get(base+"/originals?limit=51", headers=headers).status_code == 422


def test_actual_postgres_original_evidence_replay_and_full_audit(postgres_flow, monkeypatch):
    engine, institute, _, service = postgres_flow
    check(engine, institute, service, monkeypatch)


def test_postgres_concurrent_same_key_retains_once(postgres_flow, monkeypatch):
    engine, institute, _, service = postgres_flow
    exercise(engine, institute, service, monkeypatch); monkeypatch.setattr(originals, "utcnow", lambda: NOW)
    barrier = Barrier(2)
    def retain():
        with Session(engine) as db:
            barrier.wait(timeout=10)
            return originals.create(db, institute, declaration(), "signed-manager")
    with ThreadPoolExecutor(max_workers=2) as executor:
        one, two = list(executor.map(lambda _: retain(), range(2)))
    assert one == two
    with Session(engine) as db: assert db.scalar(select(func.count()).select_from(ScenarioOriginal)) == 1


def test_failed_transaction_rolls_back_and_lost_ack_recovers_committed_original(client, monkeypatch):
    institute, _, services = _bootstrap_reference_data(client)
    exercise(main_module.engine, institute, services[0]["id"], monkeypatch); monkeypatch.setattr(originals, "utcnow", lambda: NOW)
    with Session(main_module.engine) as db:
        old_flush = db.flush
        monkeypatch.setattr(db, "flush", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("Forced failed save")))
        with pytest.raises(RuntimeError): originals.create(db, institute, declaration(), "signed-manager")
        monkeypatch.setattr(db, "flush", old_flush)
        assert db.scalar(select(func.count()).select_from(ScenarioOriginal)) == 0
        old_commit = db.commit
        def lost_ack(): old_commit(); raise ConnectionError("Committed response lost")
        monkeypatch.setattr(db, "commit", lost_ack)
        with pytest.raises(ConnectionError): originals.create(db, institute, declaration(), "signed-manager")
        monkeypatch.setattr(db, "commit", old_commit)
        saved = originals.by_key(db, institute, "scenario-one")
        assert saved is not None and originals.create(db, institute, declaration(), "signed-manager") == saved
        assert db.scalar(select(func.count()).select_from(ScenarioOriginal)) == 1


def test_original_recomputed_hash_cannot_substitute_scope_capture_terms_or_calculation(client, monkeypatch):
    institute, _, services = _bootstrap_reference_data(client)
    exercise(main_module.engine, institute, services[0]["id"], monkeypatch); monkeypatch.setattr(originals, "utcnow", lambda: NOW)
    with Session(main_module.engine) as db:
        db.delete(db.get(QueueTicket, "revenue-undated")); db.commit()
        retained = originals.create(db, institute, declaration(), "signed-manager")
        row = db.get(ScenarioOriginal, retained.original["id"])
        attacks = [
            lambda raw: raw.update(institute_id="foreign"),
            lambda raw: raw.update(actor_id="another-actor"),
            lambda raw: raw.update(idempotency_key="different-key"),
            lambda raw: raw.update(reason="  Normalized reason  "),
            lambda raw: raw.update(retained=1),
            lambda raw: raw.update(validated_prediction=0),
            lambda raw: raw.update(created_at=(NOW+timedelta(seconds=1)).isoformat()),
            lambda raw: raw.update(projected_gross_minor={"numerator": "999999", "denominator": "2"}),
            lambda raw: raw.update(unavailable_reason="uncertain_amounts"),
            lambda raw: raw["evidence"]["window"].update(captured_at=(NOW-timedelta(microseconds=1)).isoformat()),
        ]
        for attack in attacks:
            raw = deepcopy(retained.original); attack(raw)
            row.original = raw; row.fingerprint = originals.fingerprint(raw); db.commit()
            with pytest.raises(HTTPException): originals.by_key(db, institute, "scenario-one")
            db.rollback()
            row.original = deepcopy(retained.original); row.fingerprint = retained.fingerprint; db.commit()
        row.fingerprint = "0"*64; db.commit()
        with pytest.raises(HTTPException): originals.require(db, institute, row.id)
        db.rollback(); row.original = deepcopy(retained.original); row.fingerprint = retained.fingerprint; db.commit()
        for payload, actor in ((declaration("new").model_copy(update={"assumptions": request().model_copy(update={"currency": "USD"})}), "signed-manager"),
            (declaration("new"), " signed-manager"), (declaration("new"), "")):
            with pytest.raises(HTTPException): originals.create(db, institute, payload, actor)
        assert db.scalar(select(func.count()).select_from(ScenarioOriginal)) == 1
