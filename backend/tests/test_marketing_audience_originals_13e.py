from datetime import timedelta
import pytest
from fastapi import HTTPException
from sqlalchemy import event,func,select
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.marketing import audience_originals as originals
from app.modules.marketing.models import AudienceOriginal,AudiencePage
from test_marketing_audiences_13b import exercise as seed
from test_crm_billing_12b import NOW
from test_postgres_scheduling_4d import postgres_flow
from test_ticket_workflow import _auth_headers,_bootstrap_reference_data

def request(key="capture"):
 return originals.Request(segments=("NEW",),channel="email",reason="Explicit audience capture",idempotency_key=key)
def exercise(engine,institute,monkeypatch):
 seed(engine,institute,monkeypatch);calls=[]
 def clock():calls.append(True);return NOW+timedelta(microseconds=2)
 monkeypatch.setattr(originals,"utcnow",clock)
 with Session(engine) as db:
  first=originals.create(db,institute,request(),"manager");assert len(calls)==1
  assert first.summary.page_count==2 and first.summary.customer_count==55 and first.summary.selected_count==55 and first.summary.eligible_count==1
  p0=originals.page(db,institute,first.id,0);p1=originals.page(db,institute,first.id,1)
  assert len(p0.observation.items)==50 and len(p1.observation.items)==5 and p1.observation.selection.after==p0.observation.next_after
  assert p0.observation.captured_at==p1.observation.captured_at==first.captured_at
  monkeypatch.setattr(originals,"utcnow",lambda:NOW-timedelta(days=1))
  assert originals.create(db,institute,request(),"manager")==first
  assert originals.original(db,institute,"capture")==first and originals.require(db,institute,first.id)==first
  for terms,actor in [(request(),"foreign"),(request().model_copy(update={"reason":"Changed reason"}),"manager")]:
   with pytest.raises(HTTPException):originals.create(db,institute,terms,actor)
  with pytest.raises(HTTPException):originals.require(db,"marketing_foreign",first.id)
  with pytest.raises(HTTPException):originals.page(db,institute,first.id,2)
  monkeypatch.setattr(originals,"utcnow",clock)
  def fail(session,context,instances):
   if any(isinstance(row,AudiencePage) and row.page_index==1 for row in session.new):raise RuntimeError("Injected second page failure")
  event.listen(db,"before_flush",fail)
  try:
   with pytest.raises(RuntimeError,match="second page failure"):originals.create(db,institute,request("rollback"),"manager")
  finally:event.remove(db,"before_flush",fail)
  assert db.scalar(select(func.count()).select_from(AudienceOriginal))==1 and db.scalar(select(func.count()).select_from(AudiencePage))==2
  assert originals.original(db,institute,"rollback") is None and originals.page(db,institute,first.id,0)==p0
  import copy
  prior=db.get(AudiencePage,(institute,first.id,0));forged=copy.deepcopy(prior.observation);forged["selection"]["channel"]="push"
  for item in forged["items"]:item["marketing_permission"]="unsupported_channel";item["eligible_by_recorded_permission"]=False
  prior.observation=forged
  with pytest.raises(HTTPException):originals.page(db,institute,first.id,1)
  db.rollback();assert originals.page(db,institute,first.id,0)==p0
  return first

def test_sqlite_atomic_capture_replay_history_and_signed_access(client,monkeypatch):
 institute,_,_=_bootstrap_reference_data(client);exercise(main_module.engine,institute,monkeypatch)
 path=f"/api/v1/marketing/institutes/{institute}/audience-captures";headers=_auth_headers("responsable_institut",institute)
 response=client.post(path,json=request("http").model_dump(mode="json"),headers=headers);assert response.status_code==200
 body=response.json();assert body["summary"]["customer_count"]==55 and not body["delivery_authorized"]
 assert client.get(path+"/original/http",headers=headers).json()==body
 assert client.get(path+"/"+body["id"],headers=headers).json()==body
 assert len(client.get(path+"/"+body["id"]+"/pages/1",headers=headers).json()["observation"]["items"])==5
 assert client.post(path,json=request("http").model_dump(mode="json"),headers=headers).json()==body
 for role,owner in [("accueil",institute),("collaboratrice",institute),("responsable_institut","foreign")]:assert client.post(path,json=request("forged").model_dump(mode="json"),headers=_auth_headers(role,owner)).status_code==403
 assert client.post(path,json=request("anonymous").model_dump(mode="json")).status_code==403

def test_postgres_atomic_capture_replay_and_history(postgres_flow,monkeypatch):exercise(postgres_flow[0],postgres_flow[1],monkeypatch)

def test_postgres_competing_same_key_capture_commits_one_original(postgres_flow,monkeypatch):
 from concurrent.futures import ThreadPoolExecutor
 engine,institute=postgres_flow[:2];seed(engine,institute,monkeypatch)
 monkeypatch.setattr(originals,"utcnow",lambda:NOW+timedelta(microseconds=2))
 def run():
  with Session(engine) as db:return originals.create(db,institute,request("concurrent"),"manager")
 with ThreadPoolExecutor(max_workers=2) as pool:
  one,two=[f.result(timeout=20) for f in [pool.submit(run),pool.submit(run)]]
 assert one==two
 with Session(engine) as db:
  assert db.scalar(select(func.count()).select_from(AudienceOriginal))==1
  assert db.scalar(select(func.count()).select_from(AudiencePage))==2
