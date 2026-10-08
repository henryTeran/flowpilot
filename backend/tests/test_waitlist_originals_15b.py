from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
from threading import Barrier
import pytest
from fastapi import HTTPException
from sqlalchemy import select, func, event
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.waitlist import originals
from app.modules.waitlist.models import DemandOriginal
from app.modules.customers.models import Customer
from app.modules.services.models import Service
from test_waitlist_matching_15a import NOW
from test_workforce_absences_11b import setup
from test_ticket_workflow import _auth_headers
from test_postgres_scheduling_4d import postgres_flow


def prepare(engine, institute, service):
    with Session(engine) as db:
        db.add(Customer(id="waitlist-customer", institute_id=institute, display_name="Fixture", phone=None,
            search_name="fixture", phone_digits="", idempotency_key="waitlist-customer", creation_fingerprint="0"*64,
            created_at=NOW-timedelta(days=3), created_by="manager"))
        db.get(Service, service).duration_min = 30
        db.commit()


def request(service, employee, key="demand-one"):
    return originals.Request(customer_id="waitlist-customer", service_id=service, duration_minutes=30,
        availability=[dict(start=NOW+timedelta(hours=1), end=NOW+timedelta(hours=2))],
        allowed_employee_ids=[employee], constraints_review="confirmed", availability_evidence="Créneau déclaré par cliente",
        constraints_evidence="Contraintes relues avec cliente", reason="Demande explicite de liste d’attente", idempotency_key=key)


def exercise(engine, institute, employee, service, monkeypatch):
    prepare(engine, institute, service)
    monkeypatch.setattr(originals, "utcnow", lambda: NOW)
    with Session(engine) as db:
        retained = originals.create(db, institute, request(service, employee), "signed-manager")
        assert retained.original["actor_id"] == "signed-manager"
        assert retained.original["state"] == "declared_only" and retained.original["action"] == "no_booking_or_contact"
        assert originals.fingerprint(retained.original) == retained.fingerprint
        for n in range(24):
            originals.create(db, institute, request(service, employee, f"demand-{n}"), "signed-manager")
        assert originals.audit(db, institute).total == 25
        assert len(originals.audit(db, institute).originals) == 20
        assert len(originals.audit(db, institute, 20).originals) == 5
        # Current source mutations do not rewrite an independently retained declaration.
        db.get(Service, service).status = "inactive"
        db.get(Customer, "waitlist-customer").created_at = NOW+timedelta(days=1)
        db.commit()
    monkeypatch.setattr(originals, "utcnow", lambda: NOW+timedelta(days=100))
    with Session(engine) as db:
        assert originals.create(db, institute, request(service, employee), "signed-manager") == retained
        assert originals.by_key(db, institute, "demand-one") == retained
        assert originals.require(db, institute, retained.original["id"]) == retained
        assert originals.by_key(db, institute, "absent") is None
        for body, actor in ((request(service, employee), "other"),
                (request(service, employee).model_copy(update={"reason": "Different reason"}), "signed-manager")):
            with pytest.raises(HTTPException): originals.create(db, institute, body, actor)
        # Rehashed logical alteration off the requested page refuses the whole audit.
        victim = db.scalar(select(DemandOriginal).order_by(DemandOriginal.created_at.desc(), DemandOriginal.id.desc()).limit(1))
        before = deepcopy(victim.original); before_hash = victim.fingerprint
        raw = deepcopy(victim.original); raw["source"]["duration_minutes"] = 31
        victim.original = raw; victim.fingerprint = originals.fingerprint(raw); db.commit()
        with pytest.raises(HTTPException): originals.audit(db, institute, 0, 1)
        db.rollback()
        victim.original = before; victim.fingerprint = before_hash; db.commit()
        return retained


def test_sqlite_retention_scope_and_replay(client, monkeypatch):
    institute, employee, service, _, _ = setup(client)
    retained = exercise(main_module.engine, institute, employee, service, monkeypatch)
    base = f"/api/v1/waitlist/institutes/{institute}"
    headers = _auth_headers("responsable_institut", institute)
    response = client.get(base+"/original-by-key", params={"key": "demand-one"}, headers=headers)
    assert response.status_code == 200 and response.json() == retained.model_dump(mode="json")
    for role, owner in (("accueil", institute), ("collaboratrice", institute), ("responsable_institut", "foreign")):
        denied = _auth_headers(role, owner)
        for path in ("/originals", "/original-by-key?key=demand-one", f"/originals/{retained.original['id']}"):
            assert client.get(base+path, headers=denied).status_code == 403
        assert client.post(base+"/originals", headers=denied, json=request(service, employee).model_dump(mode="json")).status_code == 403
    assert client.get(base+"/originals").status_code == 403
    for field in ("actor_id", "created_at", "source", "institute_id"):
        assert client.post(base+"/originals", headers=headers,
            json={**request(service, employee).model_dump(mode="json"), field: "injected"}).status_code == 422
    assert client.get(base+"/originals?limit=51", headers=headers).status_code == 422


def test_actual_postgres_retention_and_full_cohort(postgres_flow, monkeypatch):
    exercise(*postgres_flow, monkeypatch)


def test_signed_write_and_lost_ack_recovery(client, monkeypatch):
    institute, employee, service, _, _ = setup(client)
    prepare(main_module.engine, institute, service)
    monkeypatch.setattr(originals, "utcnow", lambda: NOW)
    base = f"/api/v1/waitlist/institutes/{institute}"
    headers = _auth_headers("responsable_institut", institute)
    body = request(service, employee).model_dump(mode="json")
    receipt = client.post(base+"/originals", headers=headers, json=body)
    assert receipt.status_code == 200, receipt.text
    assert receipt.json()["original"]["actor_id"] == "test-user"
    assert client.post(base+"/originals", headers=headers, json=body).json() == receipt.json()
    assert client.get(base+"/original-by-key", headers=headers, params={"key": "demand-one"}).json() == receipt.json()
    assert client.get(base+f"/originals/{receipt.json()['original']['id']}", headers=headers).json() == receipt.json()
    with Session(main_module.engine) as db:
        assert db.scalar(select(func.count()).select_from(DemandOriginal)) == 1


def test_actual_postgres_same_key_race(postgres_flow, monkeypatch):
    engine, institute, employee, service = postgres_flow
    prepare(engine, institute, service)
    monkeypatch.setattr(originals, "utcnow", lambda: NOW)
    barrier = Barrier(2)
    def run(_):
        with Session(engine) as db:
            barrier.wait(timeout=10)
            return originals.create(db, institute, request(service, employee), "signed")
    with ThreadPoolExecutor(max_workers=2) as pool:
        receipts = list(pool.map(run, range(2)))
    assert receipts[0] == receipts[1]
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(DemandOriginal)) == 1


def test_actual_postgres_rollback_and_committed_lost_ack(postgres_flow, monkeypatch):
    engine, institute, employee, service = postgres_flow
    prepare(engine, institute, service)
    monkeypatch.setattr(originals, "utcnow", lambda: NOW)
    with Session(engine) as db:
        def fail_flush(session, context):
            raise RuntimeError("forced flush failure")
        event.listen(db, "after_flush", fail_flush)
        try:
            with pytest.raises(RuntimeError, match="forced flush"):
                originals.create(db, institute, request(service, employee), "signed")
        finally:
            event.remove(db, "after_flush", fail_flush)
        assert db.scalar(select(func.count()).select_from(DemandOriginal)) == 0
        commit = db.commit
        def lost_ack():
            commit()
            raise RuntimeError("committed acknowledgement lost")
        monkeypatch.setattr(db, "commit", lost_ack)
        with pytest.raises(RuntimeError, match="acknowledgement lost"):
            originals.create(db, institute, request(service, employee), "signed")
    with Session(engine) as db:
        original = originals.by_key(db, institute, "demand-one")
        assert original is not None
        assert originals.create(db, institute, request(service, employee), "signed") == original
        assert db.scalar(select(func.count()).select_from(DemandOriginal)) == 1


def test_invalid_sources_and_rollback_leave_no_original(client, monkeypatch):
    institute, employee, service, _, _ = setup(client)
    prepare(main_module.engine, institute, service)
    monkeypatch.setattr(originals, "utcnow", lambda: NOW)
    with Session(main_module.engine) as db:
        for changes in (dict(duration_minutes=31), dict(allowed_employee_ids=["foreign"]),
                dict(customer_id="foreign"), dict(service_id="foreign"),
                dict(availability=[dict(start=NOW-timedelta(hours=2), end=NOW-timedelta(hours=1))])):
            with pytest.raises(HTTPException):
                originals.create(db, institute, request(service, employee).model_copy(update=changes), "signed")
        def fail_flush(session, context):
            raise RuntimeError("forced flush failure")
        event.listen(db, "after_flush", fail_flush)
        try:
            with pytest.raises(RuntimeError, match="forced flush"):
                originals.create(db, institute, request(service, employee), "signed")
        finally:
            event.remove(db, "after_flush", fail_flush)
        assert db.scalar(select(func.count()).select_from(DemandOriginal)) == 0
        assert originals.by_key(db, institute, "demand-one") is None


def test_rehashed_claim_identity_and_chronology_tampering(client, monkeypatch):
    institute, employee, service, _, _ = setup(client)
    prepare(main_module.engine, institute, service)
    monkeypatch.setattr(originals, "utcnow", lambda: NOW)
    with Session(main_module.engine) as db:
        receipt = originals.create(db, institute, request(service, employee), "signed")
        row = db.get(DemandOriginal, receipt.original["id"])
        for attack in (lambda raw: raw.update(actor_id="other"), lambda raw: raw.update(action="booked"),
                lambda raw: raw["source"].update(registered_at=(NOW+timedelta(microseconds=1)).isoformat()),
                lambda raw: raw["demand"].update(institute_id="foreign")):
            raw = deepcopy(receipt.original); attack(raw)
            row.original = raw; row.fingerprint = originals.fingerprint(raw); db.commit()
            with pytest.raises(HTTPException): originals.by_key(db, institute, "demand-one")
            db.rollback()
        row.original = deepcopy(receipt.original); row.fingerprint = "0"*64; db.commit()
        with pytest.raises(HTTPException): originals.require(db, institute, row.id)
