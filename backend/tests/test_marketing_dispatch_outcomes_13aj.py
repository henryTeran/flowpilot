from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import pytest
from fastapi import HTTPException
from sqlalchemy import event, select, func
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.marketing import dispatch_outcomes as service, dispatch_intents, provider, contact_originals
from app.modules.marketing.models import DispatchOutcome, DispatchHead
from test_marketing_recipient_observations_13z import setup
from test_marketing_dispatch_intents_13ai import configure, body as intent_body
from test_crm_billing_12b import NOW
from test_postgres_scheduling_4d import postgres_flow
from test_ticket_workflow import _auth_headers, _bootstrap_reference_data
from test_marketing_contact_originals_13y import body as contact_body

def fixture(engine, institute, monkeypatch):
    _, approval, contact = setup(engine, institute, monkeypatch); configure(institute, monkeypatch)
    monkeypatch.setattr(service, "utcnow", lambda: NOW + timedelta(microseconds=5))
    with Session(engine) as db: return dispatch_intents.prepare(db, institute, intent_body(approval, contact), "manager")

def body(intent, key="unknown", previous=None, status="unknown", reference=None):
    result = provider.Result(account=intent.submission.account, idempotency_key=intent.submission.idempotency_key, request_fingerprint=intent.request_fingerprint,
        status=status, provider_message_id=reference, observed_at=NOW + timedelta(microseconds=4))
    return service.Request(intent_id=intent.id, expected_previous_id=previous, result=result, reason="Explicit trusted adapter observation", idempotency_key=key)

def exercise(engine, institute, monkeypatch):
    intent = fixture(engine, institute, monkeypatch)
    with Session(engine) as db:
        assert service.current(db, institute, intent.id) is None
        first = service.append(db, institute, body(intent), "worker")
        assert service.require(db, institute, intent.id, first.id) == first
        pending = body(intent, "accepted", first.id, "accepted", "message")
        def fail(session, context, instances):
            if any(isinstance(r, DispatchHead) for r in session.dirty): raise RuntimeError("Injected outcome head failure")
        event.listen(db, "before_flush", fail)
        try:
            with pytest.raises(RuntimeError): service.append(db, institute, pending, "worker")
        finally: event.remove(db, "before_flush", fail)
        assert service.original(db, institute, intent.id, "accepted") is None
        assert service.current(db, institute, intent.id) == first
        accepted = service.append(db, institute, pending, "worker")
        assert service.current(db, institute, intent.id) == accepted
        assert service.require(db, institute, intent.id, first.id) == first
        with monkeypatch.context() as guarded:
            def fail_replay(*args): raise AssertionError("Historical replay consulted current outcome/clock")
            guarded.setattr(service, "utcnow", fail_replay); guarded.setattr(service, "current", fail_replay)
            assert service.append(db, institute, body(intent), "worker") == first
        for request, actor in [(body(intent), "other"), (body(intent).model_copy(update={"reason": "Other reason"}), "worker"),
                (body(intent, "regress", accepted.id), "worker"), (body(intent, "stale", first.id, "accepted", "message"), "worker")]:
            with pytest.raises(HTTPException): service.append(db, institute, request, actor)
        page = service.audit(db, institute, intent.id, 1, 1)
        assert page.total == 2 and len(page.items) == 1
        assert service.audit(db, institute, intent.id, 2, 1).items == ()
        assert db.scalar(select(func.count()).select_from(DispatchOutcome)) == 2
        row = db.get(DispatchOutcome, accepted.id); saved = row.result; row.result = {**saved, "request_fingerprint": "0" * 64}; db.commit()
        with pytest.raises(HTTPException): service.current(db, institute, intent.id)
        row.result = saved; db.commit()
    return intent, accepted

def test_sqlite_outcomes_history_recovery_atomicity_and_readonly_http(client, monkeypatch):
    institute, _, _ = _bootstrap_reference_data(client); intent, accepted = exercise(main_module.engine, institute, monkeypatch)
    path = f"/api/v1/marketing/institutes/{institute}/dispatch-intents/{intent.id}/outcomes"; headers = _auth_headers("responsable_institut", institute)
    assert client.get(path + "/current", headers=headers).json()["id"] == accepted.id
    assert client.get(path + "/original/accepted", headers=headers).json()["id"] == accepted.id
    assert client.get(path + "/" + accepted.id, headers=headers).status_code == 200
    assert client.get(path + "?offset=1&limit=1", headers=headers).json()["total"] == 2
    assert client.get(path + "?limit=51", headers=headers).status_code == 422
    assert client.post(path, headers=headers, json=body(intent).model_dump(mode="json")).status_code == 405
    for role, owner in [("accueil", institute), ("collaboratrice", institute), ("responsable_institut", "foreign")]:
        assert client.get(path + "/current", headers=_auth_headers(role, owner)).status_code == 403
    assert client.get(path + "/current").status_code == 403

def test_postgres_outcomes_history_recovery(postgres_flow, monkeypatch): exercise(postgres_flow[0], postgres_flow[1], monkeypatch)

@pytest.mark.parametrize("distinct_keys", [False, True])
def test_postgres_competing_observations_pin_exact_head(postgres_flow, monkeypatch, distinct_keys):
    engine, institute = postgres_flow[:2]; intent = fixture(engine, institute, monkeypatch)
    with Session(engine) as db: first = service.append(db, institute, body(intent), "worker")
    def run(index):
        with Session(engine) as db:
            try: return service.append(db, institute, body(intent, f"terminal-{index}" if distinct_keys else "terminal", first.id, "accepted", "message"), "worker")
            except HTTPException as error: return error.status_code
    with ThreadPoolExecutor(max_workers=2) as pool: values = list(pool.map(run, range(2)))
    if distinct_keys: assert sum(v == 400 for v in values) == 1
    else: assert values[0] == values[1]
    with Session(engine) as db: assert db.scalar(select(func.count()).select_from(DispatchOutcome)) == 2

def test_postgres_invalid_provider_scope_clock_and_reference_refuse(postgres_flow, monkeypatch):
    engine, institute = postgres_flow[:2]; intent = fixture(engine, institute, monkeypatch)
    with Session(engine) as db:
        for patch in ({"account": intent.submission.account.model_copy(update={"mode": "live"})}, {"idempotency_key": "other"},
                {"observed_at": NOW}, {"observed_at": NOW + timedelta(microseconds=6)}, {"delivery_confirmed": True}):
            request = body(intent).model_copy(update={"result": body(intent).result.model_copy(update=patch)})
            with pytest.raises((HTTPException, ValueError)): service.append(db, institute, request, "worker")
        first = service.append(db, institute, body(intent, reference="known-message"), "worker")
        with pytest.raises(HTTPException): service.append(db, institute, body(intent, "changed", first.id, "accepted", "other-message"), "worker")
        rejected = service.append(db, institute, body(intent, "rejected", first.id, "rejected", "known-message"), "worker")
        assert rejected.request.result.status == "rejected" and not rejected.request.result.delivery_confirmed
        contact = contact_originals.create(db, institute, "aud_054", contact_body(institute, "aud_054", "other-outcome-contact"), "manager")
        request = intent.request.model_copy(update={"customer_id": "aud_054", "expected_contact_id": contact.id, "idempotency_key": "other-outcome-intent"})
        other = dispatch_intents.prepare(db, institute, request, "manager")
        with pytest.raises(HTTPException): service.original(db, institute, other.id, "unknown")
        with pytest.raises(HTTPException): service.require(db, institute, other.id, rejected.id)
        assert service.current(db, institute, other.id) is None
        chain = []
        for index in range(3):
            chain.append(service.append(db, institute, body(other, f"cycle-{index}", chain[-1].id if chain else None), "worker"))
        # Equal clocks and valid owned FKs alone cannot establish a causal chain.
        row = db.get(DispatchOutcome, chain[0].id); row.previous_id = chain[-1].id; db.commit()
        with pytest.raises(HTTPException): service.audit(db, institute, other.id)
