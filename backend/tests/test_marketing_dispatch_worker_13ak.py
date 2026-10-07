from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event
import pytest
from fastapi import HTTPException
from sqlalchemy import event, select, func
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.marketing import dispatch_worker as worker, dispatch_outcomes, contact_originals, provider, campaign_originals
from app.modules.marketing.models import DispatchOutcome, DispatchHead
from test_marketing_dispatch_outcomes_13aj import fixture
from test_marketing_contact_originals_13y import body as contact_body
from test_crm_billing_12b import NOW
from test_postgres_scheduling_4d import postgres_flow
from test_ticket_workflow import _bootstrap_reference_data

class Fake:
    def __init__(self, engine, institute, intent):
        self.engine, self.institute, self.intent = engine, institute, intent
        self.submits = 0; self.reconciles = 0; self.saved = None; self.lose = False; self.invalid = False
    def observed(self, request):
        result = provider.Result(account=request.account, idempotency_key=request.idempotency_key, request_fingerprint=provider.fingerprint(request),
            status="accepted", provider_message_id="fixture-message", observed_at=NOW + timedelta(microseconds=5))
        return result.model_copy(update={"request_fingerprint": "0" * 64}) if self.invalid else result
    def submit(self, request):
        with Session(self.engine) as db:
            # Independent connection proves the decision committed before I/O.
            assert dispatch_outcomes.current(db, self.institute, self.intent.id).request.result.status == "unknown"
        self.submits += 1; self.saved = self.observed(request)
        if self.lose: raise TimeoutError("provider committed acceptance but response lost")
        return self.saved
    def reconcile(self, request):
        self.reconciles += 1
        return self.saved or provider.Result(account=request.account, idempotency_key=request.idempotency_key, request_fingerprint=provider.fingerprint(request),
            status="unknown", provider_message_id=None, observed_at=NOW + timedelta(microseconds=5))

def declare_send(engine, institute, intent):
    with Session(engine) as db:
        return campaign_originals.execute(db, institute, campaign_originals.Request(action="send",
            campaign_id=intent.request.campaign_id, expected_revision_id=intent.request.expected_revision_id,
            content=None, reason="Explicit signed SEND declaration", idempotency_key="worker-send"), "manager")

def configured(engine, institute, monkeypatch):
    intent = fixture(engine, institute, monkeypatch); monkeypatch.setattr(worker, "utcnow", lambda: NOW + timedelta(microseconds=5))
    declare_send(engine, institute, intent)
    adapter = Fake(engine, institute, intent)
    factory = lambda: Session(engine)
    resolve = lambda account: worker.Binding(account, adapter)
    return intent, adapter, lambda: worker.run(factory, institute, intent.id, "worker", resolve)

def exercise(engine, institute, monkeypatch):
    intent, adapter, run = configured(engine, institute, monkeypatch)
    adapter.lose = True
    first = run(); assert first.operation == "uncertain" and first.outcome.request.result.status == "unknown" and adapter.submits == 1
    # Withdrawal cannot erase an already uncertain provider attempt. Recovery only reads provider status.
    with Session(engine) as db:
        contact_originals.create(db, institute, "aud_000", contact_body(institute, "aud_000", "worker-withdraw", intent.request.expected_contact_id, "refused"), "manager")
    second = run(); assert second.operation == "reconcile_observed" and second.outcome.request.result.status == "accepted"
    assert adapter.submits == 1 and adapter.reconciles == 1
    assert run().operation == "terminal" and adapter.submits == 1 and adapter.reconciles == 1
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(DispatchOutcome)) == 2
        assert dispatch_outcomes.require(db, institute, intent.id, first.outcome.id) == first.outcome

def test_sqlite_worker_commits_before_io_and_recovers_lost_acceptance(client, monkeypatch):
    institute, _, _ = _bootstrap_reference_data(client); exercise(main_module.engine, institute, monkeypatch)

def test_postgres_worker_commits_before_io_and_recovers_lost_acceptance(postgres_flow, monkeypatch):
    exercise(postgres_flow[0], postgres_flow[1], monkeypatch)

def test_postgres_withdrawal_before_decision_never_calls_provider(postgres_flow, monkeypatch):
    engine, institute = postgres_flow[:2]; intent, adapter, run = configured(engine, institute, monkeypatch)
    with Session(engine) as db:
        contact_originals.create(db, institute, "aud_000", contact_body(institute, "aud_000", "withdraw-before", intent.request.expected_contact_id, "refused"), "manager")
    with pytest.raises(HTTPException): run()
    assert adapter.submits == adapter.reconciles == 0
    with Session(engine) as db: assert dispatch_outcomes.current(db, institute, intent.id) is None

def test_postgres_concurrent_workers_submit_once_and_do_not_hold_institute_during_io(postgres_flow, monkeypatch):
    engine, institute = postgres_flow[:2]; intent, adapter, run = configured(engine, institute, monkeypatch)
    entered, release = Event(), Event(); original = adapter.submit
    def blocked(request):
        entered.set(); assert release.wait(10); return original(request)
    adapter.submit = blocked
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(run); assert entered.wait(10)
        second = pool.submit(run).result(timeout=10)
        assert second.operation == "reconcile_observed" and second.outcome.request.result.status == "unknown"
        release.set(); assert first.result(timeout=10).outcome.request.result.status == "accepted"
    assert adapter.submits == adapter.reconciles == 1

def test_postgres_invalid_result_and_persistence_failure_keep_original_decision(postgres_flow, monkeypatch):
    engine, institute = postgres_flow[:2]; intent, adapter, run = configured(engine, institute, monkeypatch)
    adapter.invalid = True
    assert run().operation == "uncertain" and adapter.submits == 1
    adapter.invalid = False; adapter.saved = adapter.observed(intent.submission)
    def fail(session, context, instances):
        if any(isinstance(r, DispatchHead) for r in session.dirty): raise RuntimeError("Injected result retention failure")
    event.listen(Session, "before_flush", fail)
    try:
        with pytest.raises(RuntimeError): run()
    finally: event.remove(Session, "before_flush", fail)
    with Session(engine) as db: assert dispatch_outcomes.current(db, institute, intent.id).request.result.status == "unknown"
    assert run().outcome.request.result.status == "accepted" and adapter.submits == 1 and adapter.reconciles == 2

def test_postgres_crash_before_submission_reconciles_unknown_without_resubmitting(postgres_flow, monkeypatch):
    engine, institute = postgres_flow[:2]; intent, adapter, run = configured(engine, institute, monkeypatch)
    class SimulatedCrash(BaseException): pass
    def crash(request): raise SimulatedCrash()
    adapter.submit = crash
    with pytest.raises(SimulatedCrash): run()
    assert run().operation == "reconcile_observed"
    assert adapter.submits == 0 and adapter.reconciles == 1
    with Session(engine) as db:
        assert dispatch_outcomes.current(db, institute, intent.id).request.result.status == "unknown"

def test_postgres_pre_io_guards_and_commit_failure_never_call_provider(postgres_flow, monkeypatch):
    engine, institute = postgres_flow[:2]; intent, adapter, run = configured(engine, institute, monkeypatch)
    with monkeypatch.context() as guarded:
        guarded.setattr(worker.dispatch_intents.settings, "MARKETING_ACCOUNTS_JSON", "[]")
        with pytest.raises(HTTPException): run()
    def wrong_binding(account): return worker.Binding(account.model_copy(update={"sender_id": "other"}), adapter)
    with pytest.raises(HTTPException): worker.run(lambda: Session(engine), institute, intent.id, "worker", wrong_binding)
    def fail(session, context, instances):
        if any(isinstance(r, DispatchOutcome) for r in session.new): raise RuntimeError("Injected decision commit failure")
    event.listen(Session, "before_flush", fail)
    try:
        with pytest.raises(RuntimeError): run()
    finally: event.remove(Session, "before_flush", fail)
    assert adapter.submits == adapter.reconciles == 0
    with Session(engine) as db: assert dispatch_outcomes.current(db, institute, intent.id) is None
    assert run().outcome.request.result.status == "accepted" and adapter.submits == 1
    # A missing head is corruption, never permission to repeat an existing decision.
    with Session(engine) as db:
        db.delete(db.get(DispatchHead, (institute, intent.id))); db.commit()
    with pytest.raises(HTTPException): run()
    assert adapter.submits == 1
