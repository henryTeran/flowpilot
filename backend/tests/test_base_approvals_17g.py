from copy import deepcopy
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from fastapi import HTTPException
from sqlalchemy import select, func, event
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.base import approvals, sensitive_originals as operations, sensitive_capabilities as sensitive
from app.modules.base.models import ApprovalOriginal
from app.modules.appointments.models import Appointment, BookingEvent
from app.modules.appointments.schemas import AppointmentUpdate
from app.modules.appointments.service import update_appointment
from test_base_sensitive_originals_17f import prepared
from test_ticket_workflow import _auth_headers, _bootstrap_reference_data
from test_postgres_scheduling_4d import postgres_flow


def retained(flow):
    principal, request = prepared(*flow)
    with Session(flow[0]) as db:
        receipt = operations.create(db, principal, principal.institute_id, request)
    return principal, receipt


def terms(receipt, decision="approve", previous=None, key="approval-one"):
    return approvals.Request(operation_id=receipt.original["id"], operation_fingerprint=receipt.fingerprint,
        previous_id=previous.original["id"] if previous else None, previous_fingerprint=previous.fingerprint if previous else None,
        decision=decision, reason="Explicit human decision", idempotency_key=key)


def exercise(flow, monkeypatch):
    engine, institute, *_ = flow
    principal, receipt = retained(flow)
    with Session(engine) as db:
        assert approvals.state(db, principal, institute, receipt.original["id"]).status == "pending"
        approval = approvals.decide(db, principal, institute, terms(receipt))
        assert approval.fingerprint == approvals.fingerprint(approval.original)
        assert approval.original["actor_id"] == principal.actor_id
        assert approval.original["checked_state_fingerprint"] == receipt.original["expected_state_fingerprint"]
        assert approvals.state(db, principal, institute, receipt.original["id"]).status == "approved"
        assert approvals.by_key(db, principal, institute, "approval-one") == approval
        assert approvals.by_key(db, principal, institute, "absent") is None
        with pytest.raises(HTTPException): approvals.decide(db, principal, institute, terms(receipt, "revoke", key="stale-predecessor"))
        revoked = approvals.decide(db, principal.model_copy(update={"actor_id": "other-manager"}), institute,
            terms(receipt, "revoke", approval, "revoke-one"))
        state = approvals.state(db, principal, institute, receipt.original["id"])
        assert state.status == "revoked" and state.decisions == (approval, revoked)
        with pytest.raises(HTTPException): approvals.decide(db, principal, institute, terms(receipt, "approve", revoked, "terminal"))
        def no_source(*args): raise AssertionError("Historical recovery cannot recapture source")
        monkeypatch.setattr(sensitive, "preview", no_source)
        assert approvals.decide(db, principal, institute, terms(receipt)) == approval
        assert approvals.by_key(db, principal, institute, "approval-one") == approval
        for request, actor in [(terms(receipt).model_copy(update={"reason": "Changed decision reason"}), principal),
                (terms(receipt), principal.model_copy(update={"actor_id": "other-manager"}))]:
            with pytest.raises(HTTPException): approvals.decide(db, actor, institute, request)
        row = db.get(ApprovalOriginal, revoked.original["id"])
        for attack in (lambda raw: raw.update(previous_fingerprint="0"*64), lambda raw: raw.update(actor_id="invented"),
                lambda raw: raw.update(decision="approve")):
            bad = deepcopy(revoked.original); attack(bad)
            row.original = bad; row.fingerprint = approvals.fingerprint(bad); db.commit()
            with pytest.raises(HTTPException): approvals.by_key(db, principal, institute, "approval-one")
            db.rollback(); row = db.get(ApprovalOriginal, revoked.original["id"])
        row.original = deepcopy(revoked.original); row.fingerprint = revoked.fingerprint; db.commit()
        assert approvals.state(db, principal, institute, receipt.original["id"]).status == "revoked"
        assert db.get(Appointment, receipt.original["selection"]["appointment_id"]).status == "scheduled"
        assert db.scalar(select(func.count()).select_from(BookingEvent)) == 1


def test_sqlite_approve_revoke_chain_recovery_and_tamper(client, monkeypatch):
    institute, employees, services = _bootstrap_reference_data(client)
    exercise((main_module.engine, institute, employees[0]["id"], services[0]["id"]), monkeypatch)


def test_actual_postgres_approve_revoke_chain_recovery_and_tamper(postgres_flow, monkeypatch):
    exercise(postgres_flow, monkeypatch)


def test_changed_and_expired_approvals_refuse_but_explicit_decline_remains_possible(client, monkeypatch):
    institute, employees, services = _bootstrap_reference_data(client)
    principal, receipt = retained((main_module.engine, institute, employees[0]["id"], services[0]["id"]))
    with Session(main_module.engine) as db:
        update_appointment(db, receipt.original["selection"]["appointment_id"], AppointmentUpdate(notes="Changed private note"), "peer")
        with pytest.raises(HTTPException): approvals.decide(db, principal, institute, terms(receipt))
        monkeypatch.setattr(approvals, "utcnow", lambda: operations.Original.model_validate(receipt.original).valid_until+timedelta(minutes=1))
        with pytest.raises(HTTPException): approvals.decide(db, principal, institute, terms(receipt, key="expired"))
        def no_source(*args): raise AssertionError("Decline must not need current business eligibility")
        monkeypatch.setattr(sensitive, "preview", no_source)
        declined = approvals.decide(db, principal, institute, terms(receipt, "decline", key="decline"))
        state = approvals.state(db, principal, institute, receipt.original["id"])
        assert state.status == "declined" and state.expired
        assert declined.original["source_checked_at"] is None
        assert db.scalar(select(func.count()).select_from(ApprovalOriginal)) == 1


def test_signed_approval_scope_identity_and_exact_fingerprints(client):
    institute, employees, services = _bootstrap_reference_data(client)
    principal, receipt = retained((main_module.engine, institute, employees[0]["id"], services[0]["id"]))
    prefix = f"/api/v1/base/institutes/{institute}"
    headers = _auth_headers("responsable_institut", institute)
    body = terms(receipt).model_dump(mode="json")
    for role, owner in [("accueil", institute), ("collaboratrice", institute), ("direction", institute), ("super_admin", institute), ("responsable_institut", "foreign")]:
        denied = _auth_headers(role, owner)
        assert client.post(prefix+"/approvals", json=body, headers=denied).status_code == 403
        assert client.get(prefix+"/approval-by-key?key=approval-one", headers=denied).status_code == 403
        assert client.get(prefix+"/sensitive-operations/"+receipt.original["id"]+"/approval-state", headers=denied).status_code == 403
    assert client.post(prefix+"/approvals", json=body).status_code == 403
    for field in ("actor_id", "approved", "execute", "source_checked_at", "checked_state_fingerprint", "sql"):
        assert client.post(prefix+"/approvals", json={**body, field: "injected"}, headers=headers).status_code == 422
    assert client.post(prefix+"/approvals", json={**body, "operation_fingerprint": "0"*64}, headers=headers).status_code == 400
    assert client.post(prefix+"/approvals", json={**body, "decision": "execute"}, headers=headers).status_code == 422
    response = client.post(prefix+"/approvals", json=body, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["original"]["actor_id"] == "test-user"
    state = client.get(prefix+"/sensitive-operations/"+receipt.original["id"]+"/approval-state", headers=headers)
    assert state.status_code == 200 and state.json()["status"] == "approved"
    assert client.get(prefix+"/approval-by-key?key=approval-one", headers=headers).json() == response.json()


@pytest.mark.parametrize("same_key", [False, True])
def test_actual_postgres_approval_races_have_one_initial_decision(postgres_flow, same_key):
    principal, receipt = retained(postgres_flow)
    engine, institute, *_ = postgres_flow; barrier = Barrier(2)
    def run(n):
        with Session(engine) as db:
            body = terms(receipt, "approve" if same_key or n == 0 else "decline", key="same" if same_key else f"decision-{n}")
            barrier.wait(timeout=10)
            try: return approvals.decide(db, principal, institute, body)
            except HTTPException as error: return error.status_code
    with ThreadPoolExecutor(max_workers=2) as pool: results = list(pool.map(run, range(2)))
    if same_key: assert results[0] == results[1]
    else: assert sum(isinstance(r, int) and r == 400 for r in results) == 1
    with Session(engine) as db: assert db.scalar(select(func.count()).select_from(ApprovalOriginal)) == 1


def test_actual_postgres_approval_rollback_and_committed_lost_ack(postgres_flow, monkeypatch):
    principal, receipt = retained(postgres_flow)
    engine, institute, *_ = postgres_flow
    with Session(engine) as db:
        def fail(*args): raise RuntimeError("forced approval flush failure")
        event.listen(db, "after_flush", fail)
        try:
            with pytest.raises(RuntimeError, match="forced approval flush"): approvals.decide(db, principal, institute, terms(receipt))
        finally: event.remove(db, "after_flush", fail)
        assert db.scalar(select(func.count()).select_from(ApprovalOriginal)) == 0
        commit = db.commit
        def lost_ack(): commit(); raise RuntimeError("committed approval acknowledgement lost")
        monkeypatch.setattr(db, "commit", lost_ack)
        with pytest.raises(RuntimeError, match="acknowledgement lost"): approvals.decide(db, principal, institute, terms(receipt))
    with Session(engine) as db:
        approval = approvals.by_key(db, principal, institute, "approval-one")
        assert approval is not None and approvals.decide(db, principal, institute, terms(receipt)) == approval
        assert approvals.state(db, principal, institute, receipt.original["id"]).status == "approved"
