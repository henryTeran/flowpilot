from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Event
from sqlalchemy import event
from app.modules.tickets.repository import lock_institute
from datetime import timedelta
import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.crm import event_sources, automation_originals, lifecycle_originals, calendar_policies
from app.modules.customers.models import Customer
from app.modules.commerce.models import CustomerPackage, PackagePlan
from app.modules.memberships.models import CustomerMembership, MembershipPlan
from app.modules.planning.models import ServiceSession
from test_crm_return_sources_12k import sources
from test_crm_billing_12b import NOW
from test_crm_automation_originals_12aa import body as automation_body
from test_crm_lifecycle_originals_12t import body, policy
from test_postgres_scheduling_4d import postgres_flow
from test_ticket_workflow import _auth_headers, _bootstrap_reference_data

def exercise(engine, institute, employee, service, monkeypatch):
    calls=[]
    def clock(): calls.append(True); return NOW
    monkeypatch.setattr(event_sources,"utcnow",clock)
    for module in (automation_originals,lifecycle_originals,calendar_policies): monkeypatch.setattr(module,"utcnow",lambda:NOW)
    with Session(engine) as db:
        sources(db,institute,employee,service)
        db.get(Customer,"customer_crm").created_at=NOW-timedelta(days=2);db.commit()
        absent=event_sources.read(db,institute,"customer_crm")
        assert absent.candidates==() and absent.diagnostics["policy_absent"]==1
        first=automation_originals.create(db,institute,automation_body(institute,rules=[{**r,"enabled":True} for r in automation_body(institute).policy.model_dump()["rules"]]),"manager")
        lifecycle_originals.create(db,institute,"customer_crm",body(institute),"manager")
        calendar_policies.create(db,institute,policy(institute),"manager")
        calls.clear();value=event_sources.read(db,institute,"customer_crm")
        assert len(calls)==1 and value.captured_at==value.lifecycle.captured_at==value.lifecycle.birthday.capture.captured_at
        assert value.policy_original==first and not value.complete_customer_history and not value.delivery_authorized
        care=[c for c in value.candidates if c.rule.trigger=="post_service"]
        assert len(care)==106 and len(value.anchors)==107  # Whole source cohort, not the existing 20-row page.
        assert next(c for c in value.candidates if c.rule.trigger=="rebooking").source.source_id=="eur"
        assert event_sources.read(db,institute,"customer_crm")==value
        db.add(PackagePlan(id="event_plan",institute_id=institute,service_id=service,name="Explicit",sessions=2,valid_days=2))
        db.add(MembershipPlan(id="event_membership_plan",institute_id=institute,name="Explicit",valid_days=3,idempotency_key="event_plan",creation_fingerprint="fixture"))
        db.flush()
        db.add(CustomerPackage(id="event_package",institute_id=institute,plan_id="event_plan",customer_id="customer_crm",service_id=service,name="Explicit",sessions=2,consumed=0,issued_at=NOW-timedelta(days=1),expires_at=NOW+timedelta(days=1),idempotency_key="event_package"))
        db.add(CustomerMembership(id="event_membership",institute_id=institute,plan_id="event_membership_plan",customer_id="customer_crm",name="Explicit",valid_days=3,issued_at=NOW-timedelta(days=1),active_from=NOW-timedelta(days=1),active_until=NOW+timedelta(days=2),idempotency_key="event_membership"))
        db.commit()
        terms=event_sources.read(db,institute,"customer_crm")
        assert {c.rule.trigger for c in terms.candidates}=={"birthday","post_service","rebooking","inactivity","package_expiry","subscription_renewal"}
        assert next(c for c in terms.candidates if c.rule.trigger=="package_expiry").source.remaining==2
        db.get(CustomerPackage,"event_package").consumed=2;db.commit()
        assert next(c for c in event_sources.read(db,institute,"customer_crm").candidates if c.rule.trigger=="package_expiry").state=="exhausted"
        db.get(ServiceSession,"care_0").real_end_time=None;db.commit()
        invalid=event_sources.read(db,institute,"customer_crm")
        assert invalid.diagnostics["care_invalid_actual_times"]==1
        assert all(c.rule.trigger not in {"post_service","rebooking","inactivity"} for c in invalid.candidates)
        with pytest.raises(HTTPException) as error: event_sources.read(db,institute,"customer_foreign")
        assert error.value.status_code==404

def test_sqlite_full_capture_and_signed_scope(client,monkeypatch):
    institute,employee,service=_bootstrap_reference_data(client)
    exercise(main_module.engine,institute,employee[0]["id"],service[0]["id"],monkeypatch)
    path=f"/api/v1/crm/institutes/{institute}/customers/customer_crm/event-sources"
    assert client.get(path,headers=_auth_headers("responsable_institut",institute)).status_code==200
    for role,owner in (("accueil",institute),("collaboratrice",institute),("responsable_institut","foreign")):
        assert client.get(path,headers=_auth_headers(role,owner)).status_code==403
    assert client.get(path).status_code==403

def test_postgres_full_capture(postgres_flow,monkeypatch):
    exercise(*postgres_flow,monkeypatch)


def test_postgres_source_capture_blocks_rule_writer_until_snapshot_complete(postgres_flow,monkeypatch):
    engine,institute,employee,service=postgres_flow
    for module in (event_sources,automation_originals,lifecycle_originals,calendar_policies): monkeypatch.setattr(module,"utcnow",lambda:NOW)
    with Session(engine) as db:
        sources(db,institute,employee,service)
        db.get(Customer,"customer_crm").created_at=NOW-timedelta(days=2);db.commit()
        first=automation_originals.create(db,institute,automation_body(institute),"manager")
    paused,release,attempted=Event(),Event(),Event()
    def observe(connection,cursor,statement,parameters,context,executemany):
        if connection.info.get("event_reader") and "FROM customer_packages" in statement and not paused.is_set():
            paused.set();assert release.wait(timeout=15)
        if not connection.info.get("event_reader") and "FROM institutes" in statement and "FOR UPDATE" in statement: attempted.set()
    def reader():
        with Session(engine) as db:
            connection=db.connection();connection.info["event_reader"]=True
            try:return event_sources.read(db,institute,"customer_crm")
            finally:connection.info.pop("event_reader",None)
    def writer():
        with Session(engine) as db:return automation_originals.create(db,institute,automation_body(institute,"correction",first.id),"manager")
    event.listen(engine,"before_cursor_execute",observe)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            reading=pool.submit(reader);assert paused.wait(timeout=10)
            writing=pool.submit(writer);assert attempted.wait(timeout=10)
            try:
                with pytest.raises(TimeoutError):writing.result(timeout=0.2)
            finally:release.set()
            snapshot=reading.result(timeout=15);corrected=writing.result(timeout=15)
        assert snapshot.policy_original==first
        with Session(engine) as db:assert event_sources.read(db,institute,"customer_crm").policy_original==corrected
    finally:release.set();event.remove(engine,"before_cursor_execute",observe)
