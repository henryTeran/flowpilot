from concurrent.futures import ThreadPoolExecutor,TimeoutError
from datetime import timedelta
from threading import Barrier,Event
import pytest
from fastapi import HTTPException
from sqlalchemy import event
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.crm import lifecycle_originals as lifecycle,calendar_policies as calendar
from app.modules.crm.lifecycle import BirthdayCalendarPolicy
from app.modules.customers.models import Customer
from test_crm_lifecycle_12s import declaration
from test_crm_billing_12b import NOW,seed
from test_postgres_scheduling_4d import postgres_flow
from test_ticket_workflow import _auth_headers,_bootstrap_reference_data

def body(institute,customer="customer_crm",key="original",previous=None,**changes):
    return lifecycle.Declaration(declaration=declaration(institute_id=institute,customer_id=customer,**changes),
        previous_id=previous,reason="Customer explicit declaration",idempotency_key=key)

def policy(institute,key="calendar",previous=None,zone="Europe/Zurich"):
    return calendar.PolicyCreate(policy=BirthdayCalendarPolicy(institute_id=institute,timezone=zone,leap_day="leap_year_only"),
        previous_policy_id=previous,reason="Explicit local calendar",idempotency_key=key)

def exercise(engine,institute,monkeypatch):
    monkeypatch.setattr(lifecycle,"utcnow",lambda: NOW);monkeypatch.setattr(calendar,"utcnow",lambda: NOW)
    with Session(engine) as db:
        seed(db,institute)
        assert lifecycle.read(db,institute,"customer_crm").unavailable_reason=="declaration_absent"
        first=lifecycle.create(db,institute,"customer_crm",body(institute),"test-user")
        assert lifecycle.read(db,institute,"customer_crm").unavailable_reason=="calendar_absent"
        original_calendar=calendar.create(db,institute,policy(institute),"test-user")
        statements=[]
        def track(conn,cursor,statement,parameters,context,executemany): statements.append(statement)
        event.listen(engine,"before_cursor_execute",track)
        try: observed=lifecycle.read(db,institute,"customer_crm")
        finally: event.remove(engine,"before_cursor_execute",track)
        assert len(statements)==6 and observed.birthday.due and not observed.delivery_authorized
        assert observed.birthday.capture.captured_at==observed.captured_at
        assert observed.original==first and observed.calendar_original==original_calendar
        second=lifecycle.create(db,institute,"customer_crm",body(institute,key="corrected",previous=first.id,birthday=None,birthday_evidence=None),"test-user")
        assert lifecycle.read(db,institute,"customer_crm").birthday.reason=="birthday_unknown"
        corrected_calendar=calendar.create(db,institute,policy(institute,"corrected",original_calendar.id,zone="UTC"),"test-user")
        assert calendar.current(db,institute)==corrected_calendar
        monkeypatch.setattr(lifecycle,"utcnow",lambda: NOW-timedelta(microseconds=1))
        monkeypatch.setattr(calendar,"utcnow",lambda: NOW-timedelta(microseconds=1))
        assert lifecycle.create(db,institute,"customer_crm",body(institute),"test-user")==first
        assert calendar.create(db,institute,policy(institute),"test-user")==original_calendar
        assert lifecycle.read(db,institute,"customer_crm").unavailable_reason=="future_declaration"
        for payload,actor in ((body(institute),"different"),(body(institute,key="stale",previous=first.id),"test-user"),
            (body(institute,key="clock",previous=second.id),"test-user"),(body(institute,customer="customer_other",key="wrong",previous=second.id),"test-user")):
            with pytest.raises(HTTPException): lifecycle.create(db,institute,"customer_crm",payload,actor)
        for payload,actor in ((policy(institute),"different"),(policy(institute,"stale",original_calendar.id),"test-user"),
            (policy(institute,"clock",corrected_calendar.id),"test-user"),(policy("crm_foreign","wrong",corrected_calendar.id),"test-user")):
            with pytest.raises(HTTPException): calendar.create(db,institute,payload,actor)
        for customer in ("customer_foreign","historical_opaque"):
            with pytest.raises(HTTPException): lifecycle.current(db,institute,customer)
        with pytest.raises(HTTPException): lifecycle.require(db,institute,"customer_other",first.id)
        assert lifecycle.original(db,institute,"customer_other","original") is None
        monkeypatch.setattr(lifecycle,"utcnow",lambda: NOW)
        monkeypatch.setattr(calendar,"utcnow",lambda: NOW+timedelta(microseconds=1))
        calendar.create(db,institute,policy(institute,"future",corrected_calendar.id),"test-user")
        assert lifecycle.read(db,institute,"customer_crm").unavailable_reason=="future_calendar"
        monkeypatch.setattr(lifecycle,"utcnow",lambda: NOW+timedelta(microseconds=1))
        db.get(Customer,"customer_crm").created_at=NOW+timedelta(microseconds=2);db.commit()
        assert lifecycle.read(db,institute,"customer_crm").unavailable_reason=="future_registration"
        assert lifecycle.require(db,institute,"customer_crm",first.id)==first

def test_sqlite_originals_calendar_read_and_signed_scope(client,monkeypatch):
    institute,_,_=_bootstrap_reference_data(client);exercise(main_module.engine,institute,monkeypatch)
    path=f"/api/v1/crm/institutes/{institute}";headers=_auth_headers("responsable_institut",institute)
    customer=path+"/customers/customer_crm"
    first=client.get(customer+"/lifecycle-declarations/original/original",headers=headers).json()
    assert client.post(customer+"/lifecycle-declarations",headers=headers,json=body(institute).model_dump()).json()==first
    assert client.get(customer+"/lifecycle-declarations/"+first["id"],headers=headers).json()==first
    assert client.get(customer+"/lifecycle",headers=headers).json()["unavailable_reason"]=="future_registration"
    assert client.get(path+"/birthday-calendar-policies/current",headers=headers).status_code==200
    assert client.post(path+"/birthday-calendar-policies",headers=headers,json=policy(institute).model_dump()).status_code==200
    for role,owner in (("accueil",institute),("collaboratrice",institute),("responsable_institut","foreign")):
        auth=_auth_headers(role,owner)
        for suffix in ("/lifecycle","/lifecycle-declarations/current"): assert client.get(customer+suffix,headers=auth).status_code==403
        assert client.post(customer+"/lifecycle-declarations",headers=auth,json=body(institute).model_dump()).status_code==403
        assert client.get(path+"/birthday-calendar-policies/current",headers=auth).status_code==403
        assert client.post(path+"/birthday-calendar-policies",headers=auth,json=policy(institute).model_dump()).status_code==403
    assert client.get(customer+"/lifecycle").status_code==403
    assert client.post(customer+"/lifecycle-declarations",headers=headers,json={**body(institute).model_dump(),"actor_id":"spoof"}).status_code==422

def test_postgres_lifecycle_originals(postgres_flow,monkeypatch):
    engine,institute,_,_=postgres_flow;exercise(engine,institute,monkeypatch)

@pytest.mark.parametrize("family",["customer","calendar"])
def test_postgres_competing_corrections_pin_predecessor(postgres_flow,monkeypatch,family):
    engine,institute,_,_=postgres_flow
    monkeypatch.setattr(lifecycle,"utcnow",lambda: NOW);monkeypatch.setattr(calendar,"utcnow",lambda: NOW)
    with Session(engine) as db:
        seed(db,institute)
        first=lifecycle.create(db,institute,"customer_crm",body(institute),"manager") if family=="customer" else calendar.create(db,institute,policy(institute),"manager")
    barrier=Barrier(2)
    def write(key):
        with Session(engine) as db:
            barrier.wait(timeout=10)
            try:
                return (lifecycle.create(db,institute,"customer_crm",body(institute,key=key,previous=first.id),"manager") if family=="customer" else calendar.create(db,institute,policy(institute,key,first.id),"manager")).id
            except HTTPException: return None
    with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(write,("a","b")))
    assert sum(r is not None for r in results)==1

def test_postgres_calendar_correction_waits_for_birthday_capture(postgres_flow,monkeypatch):
    engine,institute,_,_=postgres_flow
    monkeypatch.setattr(lifecycle,"utcnow",lambda: NOW);monkeypatch.setattr(calendar,"utcnow",lambda: NOW)
    with Session(engine) as db:
        seed(db,institute);lifecycle.create(db,institute,"customer_crm",body(institute),"manager")
        first=calendar.create(db,institute,policy(institute),"manager")
    paused,release,attempted=Event(),Event(),Event()
    def track(connection,cursor,statement,parameters,context,executemany):
        if connection.info.get("birthday_reader") and "FROM crm_birthday_policy_heads" in statement:
            paused.set();assert release.wait(timeout=15)
        if not connection.info.get("birthday_reader") and "FROM institutes" in statement and "FOR UPDATE" in statement: attempted.set()
    def reader():
        with Session(engine) as db:
            conn=db.connection();conn.info["birthday_reader"]=True
            try: return lifecycle.read(db,institute,"customer_crm")
            finally: conn.info.pop("birthday_reader",None)
    def writer():
        with Session(engine) as db: return calendar.create(db,institute,policy(institute,"correction",first.id,zone="UTC"),"manager")
    event.listen(engine,"before_cursor_execute",track)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            reading=pool.submit(reader);assert paused.wait(timeout=10)
            writing=pool.submit(writer);assert attempted.wait(timeout=10)
            try:
                with pytest.raises(TimeoutError): writing.result(timeout=0.2)
            finally: release.set()
            before=reading.result(timeout=15);correction=writing.result(timeout=15)
        assert before.calendar_original==first and before.birthday.policy.timezone=="Europe/Zurich"
        with Session(engine) as db:
            after=lifecycle.read(db,institute,"customer_crm");assert after.calendar_original==correction and after.birthday.policy.timezone=="UTC"
    finally: release.set();event.remove(engine,"before_cursor_execute",track)
