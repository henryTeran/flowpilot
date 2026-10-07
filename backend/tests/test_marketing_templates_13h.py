from datetime import timedelta
import pytest
from fastapi import HTTPException
from sqlalchemy import event
from sqlalchemy.orm import Session
from app.modules.marketing.models import TemplateHead
from app.modules.marketing import templates
import app.main as main_module
from test_crm_billing_12b import NOW
from test_postgres_scheduling_4d import postgres_flow
from test_ticket_workflow import _auth_headers,_bootstrap_reference_data

def body(key="first",root=None,previous=None,text="Literal {customer_name} body"):
 return templates.Request(template_id=root,previous_id=previous,content=templates.Content(name="Explicit template",channel="email",origin="ai",subject="Literal subject",body=text),reason="Explicit template terms",idempotency_key=key)
def exercise(engine,institute,monkeypatch):
 monkeypatch.setattr(templates,"utcnow",lambda:NOW)
 with Session(engine) as db:
  first=templates.create(db,institute,body(),"manager")
  correction=body("correction",first.template_id,first.id,"Changed literal body")
  second=templates.create(db,institute,correction,"manager")
  assert second.previous_id==first.id and templates.current(db,institute,first.template_id)==second
  assert templates.require(db,institute,first.id)==first and templates.original(db,institute,"first")==first
  def fail(session,context,instances):
   if any(isinstance(row,TemplateHead) for row in session.dirty):raise RuntimeError("Injected template head failure")
  event.listen(db,"before_flush",fail)
  try:
   with pytest.raises(RuntimeError,match="head failure"):templates.create(db,institute,body("rollback",first.template_id,second.id),"manager")
  finally:event.remove(db,"before_flush",fail)
  assert templates.original(db,institute,"rollback") is None and templates.current(db,institute,first.template_id)==second
  monkeypatch.setattr(templates,"utcnow",lambda:NOW-timedelta(days=1))
  assert templates.create(db,institute,body(),"manager")==first
  for payload,actor in [(body(),"other"),(body(text="Changed"),"manager"),(body("stale",first.template_id,first.id),"manager"),(body("old-clock",first.template_id,second.id),"manager")]:
   with pytest.raises(HTTPException):templates.create(db,institute,payload,actor)
  return first

def test_sqlite_template_original_correction_replay_and_signed_roles(client,monkeypatch):
 institute,_,_=_bootstrap_reference_data(client);exercise(main_module.engine,institute,monkeypatch)
 path=f"/api/v1/marketing/institutes/{institute}/templates";headers=_auth_headers("responsable_institut",institute)
 response=client.post(path,json=body("http").model_dump(mode="json"),headers=headers);assert response.status_code==200
 value=response.json();assert value["content"]["body"]=="Literal {customer_name} body"
 assert client.get(path+"/original/http",headers=headers).json()==value
 assert client.get(path+"/"+value["id"],headers=headers).json()==value
 assert client.get(path+"/"+value["template_id"]+"/current",headers=headers).json()==value
 for role,owner in [("accueil",institute),("collaboratrice",institute),("responsable_institut","foreign")]:assert client.post(path,json=body("forged").model_dump(mode="json"),headers=_auth_headers(role,owner)).status_code==403
 assert client.post(path,json=body("anonymous").model_dump(mode="json")).status_code==403

def test_postgres_template_original_correction_replay(postgres_flow,monkeypatch):exercise(postgres_flow[0],postgres_flow[1],monkeypatch)

def test_postgres_competing_template_corrections_one_predecessor_wins(postgres_flow,monkeypatch):
 from concurrent.futures import ThreadPoolExecutor
 engine,institute=postgres_flow[:2];monkeypatch.setattr(templates,"utcnow",lambda:NOW)
 with Session(engine) as db:first=templates.create(db,institute,body(),"manager")
 def run(key):
  with Session(engine) as db:
   try:return templates.create(db,institute,body(key,first.template_id,first.id,key),"manager")
   except HTTPException as error:
    assert error.status_code==400
    return None
 with ThreadPoolExecutor(max_workers=2) as pool:results=[f.result(timeout=10) for f in [pool.submit(run,"one"),pool.submit(run,"two")]]
 assert sum(r is not None for r in results)==1
 with Session(engine) as db:
  assert templates.current(db,institute,first.template_id)==next(r for r in results if r is not None)
  assert templates.require(db,institute,first.id)==first

@pytest.mark.parametrize("channel",["email","sms","push"])
@pytest.mark.parametrize("origin",["human","ai"])
def test_template_channel_origin_and_literal_content_requirements(channel,origin):
 from pydantic import ValidationError
 value={"name":"Explicit template","channel":channel,"origin":origin,"subject":"Subject" if channel=="email" else None,"body":"Literal {customer_name}"}
 assert templates.Content(**value).body=="Literal {customer_name}"
 for change in [{"subject":None if channel=="email" else "Forbidden subject"},{"body":"   "},{"name":" template "}]:
  with pytest.raises(ValidationError):templates.Content(**{**value,**change})
 with pytest.raises(ValidationError):templates.Request(**{**body().model_dump(),"template_id":"root"})
