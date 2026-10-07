from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.crm import event_ledger, automation_originals, event_sources
from test_crm_event_ledger_12ae import seed_ledger, request
from test_crm_automation_originals_12aa import body as automation_body
from test_postgres_scheduling_4d import postgres_flow
from test_ticket_workflow import _auth_headers, _bootstrap_reference_data

def prepare(engine,institute,employee,service,monkeypatch):
    seed_ledger(engine,institute,employee,service,monkeypatch)
    with Session(engine) as db:
        original=automation_originals.current(db,institute)
        automation_originals.create(db,institute,automation_body(institute,"enabled",original.id,
            rules=[{**r,"enabled":True} for r in original.policy.model_dump()["rules"]]),"manager")
        return event_ledger.execute(db,institute,"customer_crm",request(),"manager")

def batch(key):
    return event_ledger.Request(action="process_due",event_key=None,expected_revision_id=None,reason="Explicit internal processing only",idempotency_key=key)

def exercise(engine,institute,employee,service,monkeypatch):
    first=prepare(engine,institute,employee,service,monkeypatch)
    with Session(engine) as db:
        processed=event_ledger.execute(db,institute,"customer_crm",batch("batch"),"manager")
        assert sum(r.decision.state=="processed" for r in processed.revisions)==20
        assert not processed.source.external_message_sent and not processed.source.delivery_authorized
        assert event_ledger.execute(db,institute,"customer_crm",batch("batch"),"manager")==processed
        next_batch=event_ledger.execute(db,institute,"customer_crm",batch("next"),"manager")
        assert sum(r.decision.state=="processed" for r in next_batch.revisions)==40
        assert event_ledger.require(db,institute,"customer_crm",first.id)==first
        due=next(r for r in next_batch.revisions if r.decision.state=="due")
        targeted_due=event_ledger.Request(action="process",event_key=due.event_key,expected_revision_id=due.id,reason="Explicit due processing",idempotency_key="target-due")
        one=event_ledger.execute(db,institute,"customer_crm",targeted_due,"manager")
        assert sum(r.decision.state=="processed" for r in one.revisions)==41
        assert event_ledger.execute(db,institute,"customer_crm",targeted_due,"manager")==one
        scheduled=next(r for r in next_batch.revisions if r.decision.state=="scheduled")
        targeted=event_ledger.Request(action="process",event_key=scheduled.event_key,expected_revision_id=scheduled.id,reason="Explicit targeted processing",idempotency_key="future")
        with pytest.raises(HTTPException):event_ledger.execute(db,institute,"customer_crm",targeted,"manager")
        done=next(r for r in next_batch.revisions if r.decision.state=="processed")
        with pytest.raises(HTTPException):event_ledger.execute(db,institute,"customer_crm",targeted.model_copy(update={"action":"cancel","event_key":done.event_key,"expected_revision_id":done.id,"idempotency_key":"cancel-processed"}),"manager")
        # Fresh source diagnostics suppress care work rather than processing cached due heads.
        from app.modules.planning.models import ServiceSession
        db.get(ServiceSession,"care_0").real_end_time=None;db.commit()
        blocked=event_ledger.execute(db,institute,"customer_crm",batch("invalid-source"),"manager")
        assert sum(r.decision.state=="processed" for r in blocked.revisions)<=43
        assert any(r.decision.state=="blocked" for r in blocked.revisions)

def test_sqlite_internal_batches_fresh_source_and_signed_http(client,monkeypatch):
    institute,employees,services=_bootstrap_reference_data(client)
    exercise(main_module.engine,institute,employees[0]["id"],services[0]["id"],monkeypatch)
    path=f"/api/v1/crm/institutes/{institute}/customers/customer_crm/event-captures"
    result=client.post(path,headers=_auth_headers("responsable_institut",institute),json=batch("signed-worker").model_dump())
    assert result.status_code==200 and result.json()["source"]["external_message_sent"] is False

def test_postgres_internal_batches_and_fresh_source(postgres_flow,monkeypatch):exercise(*postgres_flow,monkeypatch)

def test_postgres_two_workers_process_disjoint_occurrences(postgres_flow,monkeypatch):
    engine,institute,employee,service=postgres_flow;prepare(engine,institute,employee,service,monkeypatch)
    barrier=Barrier(2)
    def worker(key):
        with Session(engine) as db:
            barrier.wait(timeout=10)
            result=event_ledger.execute(db,institute,"customer_crm",batch(key),"manager")
            return {r.event_key for r in result.revisions if r.capture_id==result.id and r.decision.state=="processed"}
    with ThreadPoolExecutor(max_workers=2) as pool:one,two=list(pool.map(worker,("a","b")))
    assert len(one)==len(two)==20 and one.isdisjoint(two)
