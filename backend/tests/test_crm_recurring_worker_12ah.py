import json
import threading
from datetime import datetime, timezone
import pytest
from fastapi import HTTPException
from sqlalchemy.orm import sessionmaker
import app.main as main_module
from app.core.security import create_access_token
from app.modules.crm import recurring_worker as runner
from app.modules.crm.event_worker import PassRead, PassItem
from test_crm_event_worker_12af import prepare
from test_postgres_scheduling_4d import postgres_flow
from test_ticket_workflow import _bootstrap_reference_data

def token(institute="i",actor="manager",role="responsable_institut"):
    return create_access_token(actor,{"role":role,"institute_id":institute})

def test_response_loss_and_restart_reuse_pending_key_without_credential_in_journal(tmp_path):
    path=tmp_path/"worker.json";calls=[]
    def lost(factory,institute,payload,actor):calls.append(payload);raise RuntimeError("Committed response lost")
    with pytest.raises(RuntimeError):runner.run(None,"i","Explicit cadence",60,path,lambda:token(),threading.Event(),once=True,dispatch_page=lost)
    def recovered(factory,institute,payload,actor):
        calls.append(payload)
        return PassRead(institute_id=institute,after=None,next_after=None,items=(PassItem(customer_id="c",capture_id="receipt",failed=False),))
    completed=runner.run(None,"i","Explicit cadence",60,path,lambda:token(),threading.Event(),once=True,dispatch_page=recovered)
    assert calls[0]==calls[1] and completed.completed_cycles==1
    raw=path.read_text();assert "Bearer" not in raw and token() not in raw
    with pytest.raises(ValueError):runner.run(None,"i","Changed cadence",60,path,lambda:token(),threading.Event(),once=True)

def test_page_stop_restart_and_fresh_cycle_keys_with_failure_observability(tmp_path):
    path=tmp_path/"worker.json";stop=threading.Event();calls=[]
    def first(factory,institute,payload,actor):
        calls.append(payload);stop.set()
        return PassRead(institute_id=institute,after=None,next_after="a",items=(PassItem(customer_id="a",capture_id=None,failed=True),))
    state=runner.run(None,"i","Explicit cadence",1,path,lambda:token(),stop,dispatch_page=first)
    assert state.after=="a" and state.completed_cycles==0
    def last(factory,institute,payload,actor):
        calls.append(payload)
        return PassRead(institute_id=institute,after=payload.after,next_after=None,items=())
    completed=runner.run(None,"i","Explicit cadence",1,path,lambda:token(),threading.Event(),once=True,dispatch_page=last)
    assert calls[0].idempotency_key==calls[1].idempotency_key and calls[1].after=="a"
    assert completed.failed_customer_ids==("a",)
    again=runner.run(None,"i","Explicit cadence",1,path,lambda:token(),threading.Event(),once=True,dispatch_page=last,
        now=lambda:datetime(2090,1,1,tzinfo=timezone.utc))
    assert calls[2].idempotency_key!=calls[1].idempotency_key and again.completed_cycles==2

def test_scope_forgery_corrupt_state_and_double_lease_refused(tmp_path):
    path=tmp_path/"worker.json"
    for auth in (token("foreign"),token(role="accueil")):
        with pytest.raises((ValueError,HTTPException)):runner.run(None,"i","Explicit cadence",60,path,lambda:auth,threading.Event(),once=True)
    assert not path.exists()
    path.write_text("{invalid")
    with pytest.raises(ValueError):runner.run(None,"i","Explicit cadence",60,path,lambda:token(),threading.Event(),once=True)
    with runner.lease(path):
        with pytest.raises(OSError):
            with runner.lease(path):pass

def integration(engine,institute,employee,service,monkeypatch,tmp_path):
    prepare(engine,institute,employee,service,monkeypatch)
    path=tmp_path/"real-worker.json"
    result=runner.run(sessionmaker(bind=engine),institute,"Controlled recurring worker",60,path,lambda:token(institute),threading.Event(),once=True)
    assert result.completed_cycles==1 and result.failed_customer_ids==()

def test_sqlite_real_signed_worker_cycle(client,monkeypatch,tmp_path):
    institute,employees,services=_bootstrap_reference_data(client)
    integration(main_module.engine,institute,employees[0]["id"],services[0]["id"],monkeypatch,tmp_path)

def test_postgres_real_signed_worker_cycle(postgres_flow,monkeypatch,tmp_path):integration(*postgres_flow,monkeypatch,tmp_path)


def test_expired_token_stops_at_retained_page_and_forged_reply_keeps_pending_intent(tmp_path):
    expired=create_access_token("manager",{"role":"responsable_institut","institute_id":"i","exp":0})
    tokens=iter((token(),token(),expired))
    def page(factory,institute,payload,actor):return PassRead(institute_id="i",after=None,next_after="a",items=(PassItem(customer_id="a",capture_id="receipt",failed=False),))
    path=tmp_path/"expired.json"
    with pytest.raises(HTTPException):runner.run(None,"i","Explicit cadence",60,path,lambda:next(tokens),threading.Event(),dispatch_page=page)
    retained=json.loads(path.read_text());assert retained["after"]=="a" and retained["completed_cycles"]==0
    bad=tmp_path/"forged.json"
    def forged(factory,institute,payload,actor):return PassRead(institute_id="foreign",after=None,next_after=None,items=())
    with pytest.raises(ValueError):runner.run(None,"i","Explicit cadence",60,bad,lambda:token(),threading.Event(),dispatch_page=forged)
    assert json.loads(bad.read_text())["next_due_at"] is None

@pytest.mark.parametrize("database",["sqlite","postgresql"])
def test_cli_migration_preflight_requires_current_owned_schema(tmp_path,monkeypatch,database):
    from alembic import command
    from sqlalchemy import text
    from test_source_index_migration_10t import owned_engine
    with owned_engine(tmp_path,monkeypatch,database) as (engine,config):
        with pytest.raises(RuntimeError,match="explicitly migrated"):runner.verify_schema(engine)
        command.upgrade(config,"head")
        runner.verify_schema(engine)
        with engine.begin() as connection:connection.execute(text("UPDATE alembic_version SET version_num='ea5b7cd43926'"))
        with pytest.raises(RuntimeError,match="does not match"):runner.verify_schema(engine)

def test_stop_interrupts_pending_cadence_without_another_page(tmp_path):
    stop=threading.Event();completed=threading.Event();errors=[];calls=[]
    def page(factory,institute,payload,actor):
        calls.append(payload)
        return PassRead(institute_id=institute,after=None,next_after=None,items=())
    def task():
        try:runner.run(None,"i","Explicit cadence",3600,tmp_path/"stoppable.json",lambda:token(),stop,
            dispatch_page=page,notify=lambda _:completed.set())
        except Exception as error:errors.append(error)
    thread=threading.Thread(target=task);thread.start()
    try:
        assert completed.wait(timeout=2)
        stop.set();thread.join(timeout=2)
        assert not thread.is_alive() and not errors and len(calls)==1
    finally:stop.set();thread.join(timeout=2)
