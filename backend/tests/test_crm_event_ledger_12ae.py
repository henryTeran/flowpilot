from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from fastapi import HTTPException
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.crm import event_ledger, event_sources, automation_originals, lifecycle_originals, calendar_policies
from app.modules.crm.models import EventCaptureOriginal, EventRevision
from app.modules.commerce.models import CustomerPackage, PackagePlan
from app.modules.memberships.models import CustomerMembership, MembershipPlan
from app.modules.customers.models import Customer
from test_crm_return_sources_12k import sources
from test_crm_billing_12b import NOW
from test_crm_automation_originals_12aa import body as automation_body
from test_crm_lifecycle_originals_12t import body, policy
from test_postgres_scheduling_4d import postgres_flow
from test_ticket_workflow import _auth_headers, _bootstrap_reference_data
from datetime import timedelta

def request(key="run",**changes):
    return event_ledger.Request(action="reconcile",event_key=None,expected_revision_id=None,reason="Explicit internal event capture",idempotency_key=key,**changes)

def seed_ledger(engine,institute,employee,service,monkeypatch):
    for module in (event_sources,automation_originals,lifecycle_originals,calendar_policies):monkeypatch.setattr(module,"utcnow",lambda:NOW)
    with Session(engine) as db:
        sources(db,institute,employee,service)
        db.get(Customer,"customer_crm").created_at=NOW-timedelta(days=2);db.commit()
        automation_originals.create(db,institute,automation_body(institute),"manager")
        lifecycle_originals.create(db,institute,"customer_crm",body(institute),"manager")
        calendar_policies.create(db,institute,policy(institute),"manager")
        db.add(PackagePlan(id="ledger_plan",institute_id=institute,service_id=service,name="Explicit",sessions=2,valid_days=2))
        db.add(MembershipPlan(id="ledger_member_plan",institute_id=institute,name="Explicit",valid_days=3,idempotency_key="ledger_plan",creation_fingerprint="fixture"))
        db.flush()
        db.add(CustomerPackage(id="ledger_package",institute_id=institute,plan_id="ledger_plan",customer_id="customer_crm",service_id=service,name="Explicit",sessions=2,consumed=0,issued_at=NOW-timedelta(days=1),expires_at=NOW+timedelta(days=1),idempotency_key="ledger_package"))
        db.add(CustomerMembership(id="ledger_membership",institute_id=institute,plan_id="ledger_member_plan",customer_id="customer_crm",name="Explicit",valid_days=3,issued_at=NOW-timedelta(days=1),active_from=NOW-timedelta(days=1),active_until=NOW+timedelta(days=2),idempotency_key="ledger_membership"))
        db.commit()

def exercise(engine,institute,employee,service,monkeypatch):
    seed_ledger(engine,institute,employee,service,monkeypatch)
    with Session(engine) as db:
        first=event_ledger.execute(db,institute,"customer_crm",request(),"manager")
        assert len(first.revisions)==111 and not first.source.delivery_authorized
        assert {r.decision.candidate.rule.trigger for r in first.revisions}=={"birthday","post_service","rebooking","inactivity","package_expiry","subscription_renewal"}
        repeated=event_ledger.execute(db,institute,"customer_crm",request("second"),"manager")
        assert [r.id for r in repeated.revisions]==[r.id for r in first.revisions]
        chosen=first.revisions[0]
        cancellation=event_ledger.Request(action="cancel",event_key=chosen.event_key,expected_revision_id=chosen.id,reason="Explicit manager cancellation",idempotency_key="cancel")
        cancelled=event_ledger.execute(db,institute,"customer_crm",cancellation,"manager")
        assert next(r for r in cancelled.revisions if r.event_key==chosen.event_key).decision.reason=="explicit_cancellation"
        assert event_ledger.require(db,institute,"customer_crm",first.id)==first
        page=event_ledger.page(db,institute,"customer_crm",20,100)
        assert page.total==111 and len(page.revisions)==11
        assert event_ledger.original(db,institute,"customer_crm","run")==first
        assert event_ledger.execute(db,institute,"customer_crm",cancellation,"manager")==cancelled
        monkeypatch.setattr(event_sources,"utcnow",lambda:NOW-timedelta(days=1))
        assert event_ledger.execute(db,institute,"customer_crm",request(),"manager")==first
        for payload,actor in ((request(),"other"),(request().model_copy(update={"reason":"Changed terms"}),"manager")):
            with pytest.raises(HTTPException):event_ledger.execute(db,institute,"customer_crm",payload,actor)
        monkeypatch.setattr(event_sources,"utcnow",lambda:NOW)
        before=db.scalar(select(func.count()).select_from(EventCaptureOriginal))
        with pytest.raises(HTTPException):event_ledger.execute(db,institute,"customer_crm",cancellation.model_copy(update={"idempotency_key":"stale"}),"manager")
        assert db.scalar(select(func.count()).select_from(EventCaptureOriginal))==before
        # Fail after the capture row is inserted, proving whole-transaction rollback.
        changed=automation_body(institute,"enabled",first.source.policy_original.id,rules=[{**r,"enabled":True} for r in first.source.policy_original.policy.model_dump()["rules"]])
        automation_originals.create(db,institute,changed,"manager")
        revision_count=db.scalar(select(func.count()).select_from(EventRevision))
        flushed=[]
        def fail(session,context,instances):
            if any(isinstance(row,EventRevision) for row in session.new):
                flushed.append(True)
                if len(flushed)==3:raise RuntimeError("Injected revision failure")
        event.listen(db,"before_flush",fail)
        try:
            with pytest.raises(RuntimeError,match="Injected"):event_ledger.execute(db,institute,"customer_crm",request("failed"),"manager")
        finally:event.remove(db,"before_flush",fail)
        assert event_ledger.original(db,institute,"customer_crm","failed") is None
        assert db.scalar(select(func.count()).select_from(EventCaptureOriginal))==before
        assert db.scalar(select(func.count()).select_from(EventRevision))==revision_count
        final=event_ledger.execute(db,institute,"customer_crm",request("recovered"),"manager")
        assert next(r for r in final.revisions if r.event_key==chosen.event_key).decision.reason=="explicit_cancellation"
        return first

def test_sqlite_atomic_replay_cancellation_history_and_http(client,monkeypatch):
    institute,employees,services=_bootstrap_reference_data(client)
    first=exercise(main_module.engine,institute,employees[0]["id"],services[0]["id"],monkeypatch)
    path=f"/api/v1/crm/institutes/{institute}/customers/customer_crm/event-captures"
    headers=_auth_headers("responsable_institut",institute)
    assert client.get(path+"/original/run",headers=headers).json()==first.model_dump(mode="json")
    assert client.get(path+"/"+first.id,headers=headers).json()==first.model_dump(mode="json")
    assert client.get(path.replace("event-captures","events"),headers=headers,params={"limit":51}).status_code==422
    signed=client.post(path,headers=headers,json=request("signed-http").model_dump())
    assert signed.status_code==200
    assert client.post(path,headers=headers,json=request("signed-http").model_dump()).json()==signed.json()
    assert client.post(path,json=request("unauthenticated").model_dump()).status_code==403
    for role,owner in (("accueil",institute),("collaboratrice",institute),("responsable_institut","foreign")):
        assert client.post(path,headers=_auth_headers(role,owner),json=request().model_dump()).status_code==403
    assert client.post(path,headers=headers,json={**request().model_dump(),"actor_id":"spoof"}).status_code==422

def test_postgres_atomic_replay_cancellation_and_history(postgres_flow,monkeypatch):exercise(*postgres_flow,monkeypatch)

def test_postgres_competing_cancellations_one_explicit_revision_wins(postgres_flow,monkeypatch):
    engine,institute,employee,service=postgres_flow;seed_ledger(engine,institute,employee,service,monkeypatch)
    with Session(engine) as db:first=event_ledger.execute(db,institute,"customer_crm",request(),"manager")
    chosen=first.revisions[0];barrier=Barrier(2)
    def write(key):
        with Session(engine) as db:
            barrier.wait(timeout=10)
            try:return event_ledger.execute(db,institute,"customer_crm",event_ledger.Request(action="cancel",event_key=chosen.event_key,expected_revision_id=chosen.id,reason="Competing explicit cancellation",idempotency_key=key),"manager").id
            except HTTPException:return None
    with ThreadPoolExecutor(max_workers=2) as pool:result=list(pool.map(write,("a","b")))
    assert sum(v is not None for v in result)==1


def test_postgres_same_key_concurrent_reconciliation_creates_one_capture(postgres_flow,monkeypatch):
    engine,institute,employee,service=postgres_flow;seed_ledger(engine,institute,employee,service,monkeypatch)
    barrier=Barrier(2)
    def write(_):
        with Session(engine) as db:
            barrier.wait(timeout=10)
            return event_ledger.execute(db,institute,"customer_crm",request(),"manager").id
    with ThreadPoolExecutor(max_workers=2) as pool:result=list(pool.map(write,("a","b")))
    assert result[0]==result[1]
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(EventCaptureOriginal))==1
        assert db.scalar(select(func.count()).select_from(EventRevision))==111
