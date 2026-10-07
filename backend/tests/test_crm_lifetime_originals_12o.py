from concurrent.futures import ThreadPoolExecutor, TimeoutError
from datetime import timedelta
from threading import Barrier, Event
import pytest
from fastapi import HTTPException
from sqlalchemy import event
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.crm import lifetime_originals as lifetime
from app.modules.customers.models import Customer
from app.modules.tickets.models import QueueTicket
from test_crm_lifetime_12n import assumptions
from test_crm_billing_12b import NOW, seed
from test_postgres_scheduling_4d import postgres_flow
from test_ticket_workflow import _auth_headers, _bootstrap_reference_data

def body(institute,customer="customer_crm",key="original",previous=None,**changes):
    return lifetime.Declaration(assumptions=assumptions(institute_id=institute,customer_id=customer,**changes),
        previous_id=previous,reason="Explicit lifetime fixture",idempotency_key=key)

def exercise(engine,institute,monkeypatch):
    monkeypatch.setattr(lifetime,"utcnow",lambda: NOW)
    with Session(engine) as db:
        seed(db,institute)
        assert lifetime.current(db,institute,"customer_crm") is None
        assert lifetime.read(db,institute,"customer_crm",NOW-timedelta(days=1)).unavailable_reason == "assumptions_absent"
        first = lifetime.create(db,institute,"customer_crm",body(institute),"test-user")
        uncertain = lifetime.read(db,institute,"customer_crm",NOW-timedelta(days=1))
        assert uncertain.scenario.unavailable_reason == "undated_closings"
        for key in ("unknown_date","unknown_currency"):
            db.get(QueueTicket,key).status = "waiting"
        db.commit()
        statements=[]
        def track(conn,cursor,statement,parameters,context,executemany): statements.append(statement)
        event.listen(engine,"before_cursor_execute",track)
        try: observed=lifetime.read(db,institute,"customer_crm",NOW-timedelta(days=1))
        finally: event.remove(engine,"before_cursor_execute",track)
        assert len(statements)==6
        assert observed.scenario.billing.closed_tickets==108
        assert observed.scenario.remaining_clv_minor.model_dump()=={"numerator":"3435","denominator":"1"}
        assert observed.original==first and observed.window.captured_at==observed.scenario.billing.window.captured_at
        assert observed.customer.customer_id=="customer_crm" and observed.customer.created_at==NOW
        db.get(QueueTicket,"at_end").paid_at=NOW+timedelta(microseconds=1)
        db.commit()
        assert lifetime.read(db,institute,"customer_crm",NOW-timedelta(days=1)).scenario.unavailable_reason=="future_closings"
        db.get(QueueTicket,"at_end").paid_at=NOW
        db.get(Customer,"customer_crm").created_at=NOW+timedelta(microseconds=1)
        db.commit()
        assert lifetime.read(db,institute,"customer_crm",NOW-timedelta(days=1)).unavailable_reason=="future_registration"
        db.get(Customer,"customer_crm").created_at=NOW
        db.commit()
        second=lifetime.create(db,institute,"customer_crm",body(institute,key="second",previous=first.id,future_relationship_cost_minor="200"),"test-user")
        assert lifetime.current(db,institute,"customer_crm")==second
        assert lifetime.require(db,institute,"customer_crm",first.id)==first
        monkeypatch.setattr(lifetime,"utcnow",lambda: NOW-timedelta(microseconds=1))
        assert lifetime.create(db,institute,"customer_crm",body(institute),"test-user")==first
        assert lifetime.read(db,institute,"customer_crm",NOW-timedelta(days=1)).unavailable_reason=="future_assumptions"
        for payload,actor in ((body(institute),"other"),(body(institute,future_relationship_cost_minor="999"),"test-user"),
            (body(institute,key="stale",previous=first.id),"test-user"),(body(institute,key="clock",previous=second.id),"test-user"),
            (body(institute,customer="customer_other",key="wrong",previous=second.id),"test-user")):
            with pytest.raises(HTTPException): lifetime.create(db,institute,"customer_crm",payload,actor)
        with pytest.raises(HTTPException): lifetime.require(db,institute,"customer_other",first.id)
        for customer in ("customer_foreign","historical_opaque"):
            with pytest.raises(HTTPException): lifetime.current(db,institute,customer)
        assert lifetime.original(db,institute,"customer_other","original") is None
        assert lifetime.current(db,institute,"customer_crm")==second

def test_sqlite_original_scenario_and_signed_scope(client,monkeypatch):
    institute,_,_=_bootstrap_reference_data(client)
    exercise(main_module.engine,institute,monkeypatch)
    path=f"/api/v1/crm/institutes/{institute}/customers/customer_crm"
    headers=_auth_headers("responsable_institut",institute)
    first=client.get(path+"/lifetime-assumptions/original/original",headers=headers).json()
    assert client.post(path+"/lifetime-assumptions",headers=headers,json=body(institute).model_dump()).json()==first
    assert client.get(path+"/lifetime-assumptions/"+first["id"],headers=headers).json()==first
    assert client.get(path+"/lifetime-scenario",headers=headers,params={"start":(NOW-timedelta(days=1)).isoformat()}).status_code==200
    assert client.get(path+"/lifetime-scenario",headers=headers,params={"start":"2026-10-06"}).status_code==400
    for role,owner in (("accueil",institute),("collaboratrice",institute),("responsable_institut","foreign")):
        auth=_auth_headers(role,owner)
        assert client.get(path+"/lifetime-assumptions/current",headers=auth).status_code==403
        assert client.post(path+"/lifetime-assumptions",headers=auth,json=body(institute).model_dump()).status_code==403
        assert client.get(path+"/lifetime-scenario",headers=auth,params={"start":NOW.isoformat()}).status_code==403
    assert client.post(path+"/lifetime-assumptions",headers=headers,json={**body(institute).model_dump(),"actor_id":"spoof"}).status_code==422
    assert client.get(path+"/lifetime-assumptions/current").status_code==403
    assert client.get(path.replace("customer_crm","customer_foreign")+"/lifetime-assumptions/current",headers=headers).status_code==404

def test_postgres_original_scenario(postgres_flow,monkeypatch):
    engine,institute,_,_=postgres_flow
    exercise(engine,institute,monkeypatch)

def test_postgres_concurrent_lifetime_corrections(postgres_flow,monkeypatch):
    engine,institute,_,_=postgres_flow
    monkeypatch.setattr(lifetime,"utcnow",lambda: NOW)
    with Session(engine) as db:
        seed(db,institute)
        first=lifetime.create(db,institute,"customer_crm",body(institute),"manager")
    barrier=Barrier(2)
    def write(key):
        with Session(engine) as db:
            barrier.wait(timeout=10)
            try: return lifetime.create(db,institute,"customer_crm",body(institute,key=key,previous=first.id),"manager").id
            except HTTPException: return None
    with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(write,("a","b")))
    assert sum(v is not None for v in results)==1
    with Session(engine) as db: assert lifetime.current(db,institute,"customer_crm").id in results

def test_postgres_correction_waits_for_complete_lifetime_capture(postgres_flow,monkeypatch):
    engine,institute,_,_=postgres_flow
    monkeypatch.setattr(lifetime,"utcnow",lambda: NOW)
    with Session(engine) as db:
        seed(db,institute)
        for key in ("unknown_date","unknown_currency"): db.get(QueueTicket,key).status="waiting"
        db.commit()
        first=lifetime.create(db,institute,"customer_crm",body(institute),"manager")
    paused,release,attempted=Event(),Event(),Event()
    def observe(connection,cursor,statement,parameters,context,executemany):
        if connection.info.get("lifetime_reader") and "FROM queue_tickets" in statement and not paused.is_set():
            paused.set(); assert release.wait(timeout=15)
        if not connection.info.get("lifetime_reader") and "FROM institutes" in statement and "FOR UPDATE" in statement: attempted.set()
    def reader():
        with Session(engine) as db:
            connection=db.connection(); connection.info["lifetime_reader"]=True
            try: return lifetime.read(db,institute,"customer_crm",NOW-timedelta(days=1))
            finally: connection.info.pop("lifetime_reader",None)
    def writer():
        with Session(engine) as db:
            return lifetime.create(db,institute,"customer_crm",body(institute,key="correction",previous=first.id,future_relationship_cost_minor="200"),"manager")
    event.listen(engine,"before_cursor_execute",observe)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            reading=pool.submit(reader); assert paused.wait(timeout=10)
            writing=pool.submit(writer); assert attempted.wait(timeout=10)
            try:
                with pytest.raises(TimeoutError): writing.result(timeout=0.2)
            finally: release.set()
            captured=reading.result(timeout=15); correction=writing.result(timeout=15)
        assert captured.original==first and captured.scenario.remaining_clv_minor.numerator=="3435"
        with Session(engine) as db:
            after=lifetime.read(db,institute,"customer_crm",NOW-timedelta(days=1))
            assert after.original==correction and after.scenario.remaining_clv_minor.numerator=="3335"
    finally:
        release.set(); event.remove(engine,"before_cursor_execute",observe)
