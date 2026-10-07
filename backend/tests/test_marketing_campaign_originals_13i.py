from datetime import timedelta
import pytest
from fastapi import HTTPException
from sqlalchemy import event
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.marketing import campaign_originals as originals,templates
from app.modules.marketing.models import CampaignHead
from test_marketing_audience_originals_13e import exercise as capture_fixture
from test_marketing_templates_13h import body as template_body
from test_crm_billing_12b import NOW
from test_postgres_scheduling_4d import postgres_flow
from test_ticket_workflow import _auth_headers,_bootstrap_reference_data

def body(capture,key="draft",root=None,previous=None,action="create",content=None):
 if action in ("create","edit") and content is None:content=originals.Content(channel="email",origin="ai",subject="Subject",body="Explicit literal campaign",audience_id=capture,template_original_id=None)
 return originals.Request(action=action,campaign_id=root,expected_revision_id=previous,content=content,reason="Explicit campaign action",idempotency_key=key)
def exercise(engine,institute,monkeypatch):
 audience=capture_fixture(engine,institute,monkeypatch)
 monkeypatch.setattr(originals,"utcnow",lambda:NOW+timedelta(microseconds=3))
 monkeypatch.setattr(templates,"utcnow",lambda:NOW)
 with Session(engine) as db:
  first=originals.execute(db,institute,body(audience.id),"manager");root=first.revision.campaign_id
  assert first.revision.content.audience.customer_ids==("aud_000","aud_054") and first.revision.state=="DRAFT"
  with pytest.raises(HTTPException):originals.execute(db,institute,body(audience.id,"skip",root,first.revision.id,"approve"),"manager")
  reviewed=originals.execute(db,institute,body(audience.id,"review",root,first.revision.id,"review"),"reviewer")
  approved=originals.execute(db,institute,body(audience.id,"approve",root,reviewed.revision.id,"approve"),"approver")
  assert approved.revision.state=="APPROVE" and approved.revision.approved_digest==approved.revision.reviewed_digest
  assert not approved.revision.delivery_authorized and not approved.revision.external_message_sent
  assert originals.current(db,institute,root)==approved and originals.require(db,institute,first.revision.id)==first
  changed=body(audience.id,"edit",root,approved.revision.id,"edit").model_copy(update={"content":body(audience.id).content.model_copy(update={"body":"Edited content"})})
  edited=originals.execute(db,institute,changed,"manager");assert edited.revision.state=="DRAFT" and edited.revision.approved_digest is None
  def fail(session,context,instances):
   if any(isinstance(row,CampaignHead) for row in session.dirty):raise RuntimeError("Injected campaign head failure")
  event.listen(db,"before_flush",fail)
  try:
   with pytest.raises(RuntimeError):originals.execute(db,institute,body(audience.id,"rollback",root,edited.revision.id,"review"),"reviewer")
  finally:event.remove(db,"before_flush",fail)
  assert originals.original(db,institute,"rollback") is None and originals.current(db,institute,root)==edited
  audit=originals.audit(db,institute,root,0,2);next_page=originals.audit(db,institute,root,2,2)
  assert audit.total==next_page.total==4 and len(audit.originals)==len(next_page.originals)==2
  assert {r.revision.id for r in audit.originals+next_page.originals}=={r.revision.id for r in (first,reviewed,approved,edited)}
  template=templates.create(db,institute,template_body(),"manager")
  bound=originals.Content(channel=template.content.channel,origin=template.content.origin,subject=template.content.subject,body=template.content.body,audience_id=audience.id,template_original_id=template.id)
  derived=originals.execute(db,institute,body(audience.id,"bound",content=bound),"manager");assert derived.revision.content.template_original_id==template.id
  with pytest.raises(HTTPException):originals.execute(db,institute,body(audience.id,"bad-template",content=bound.model_copy(update={"body":"Mismatch"})),"manager")
  with pytest.raises(HTTPException):originals.require(db,"marketing_foreign",first.revision.id)
  monkeypatch.setattr(originals,"utcnow",lambda:NOW-timedelta(days=1))
  assert originals.execute(db,institute,body(audience.id),"manager")==first
  for payload,actor in [(body(audience.id),"foreign"),(body(audience.id).model_copy(update={"reason":"Changed reason"}),"manager"),(body(audience.id,"stale",root,first.revision.id,"review"),"manager"),(body(audience.id,"old-clock",root,edited.revision.id,"review"),"manager")]:
   with pytest.raises(HTTPException):originals.execute(db,institute,payload,actor)
  return audience

def test_sqlite_campaign_chain_replay_atomicity_sources_and_signed_http(client,monkeypatch):
 institute,_,_=_bootstrap_reference_data(client);audience=exercise(main_module.engine,institute,monkeypatch)
 monkeypatch.setattr(originals,"utcnow",lambda:NOW+timedelta(microseconds=3))
 path=f"/api/v1/marketing/institutes/{institute}/campaigns";headers=_auth_headers("responsable_institut",institute)
 response=client.post(path,json=body(audience.id,"http").model_dump(mode="json"),headers=headers);assert response.status_code==200
 value=response.json();assert client.get(path+"/original/http",headers=headers).json()==value
 assert client.get(path+"/"+value["revision"]["id"],headers=headers).json()==value
 assert client.get(path+"/"+value["revision"]["campaign_id"]+"/current",headers=headers).json()==value
 assert client.get(path+"/"+value["revision"]["campaign_id"]+"/audit?limit=1",headers=headers).json()["total"]==1
 assert client.get(path+"/"+value["revision"]["campaign_id"]+"/audit?limit=51",headers=headers).status_code==422
 for role,owner in [("accueil",institute),("collaboratrice",institute),("responsable_institut","foreign")]:assert client.post(path,json=body(audience.id,"forged").model_dump(mode="json"),headers=_auth_headers(role,owner)).status_code==403
 assert client.post(path,json=body(audience.id,"anonymous").model_dump(mode="json")).status_code==403
 assert client.post(path,json={**body(audience.id,"send").model_dump(mode="json"),"action":"send"},headers=headers).status_code==422

def test_postgres_campaign_chain_replay_atomicity_sources(postgres_flow,monkeypatch):exercise(postgres_flow[0],postgres_flow[1],monkeypatch)

def test_postgres_same_key_creation_and_competing_review_are_serialized(postgres_flow,monkeypatch):
 from concurrent.futures import ThreadPoolExecutor
 engine,institute=postgres_flow[:2];audience=capture_fixture(engine,institute,monkeypatch)
 monkeypatch.setattr(originals,"utcnow",lambda:NOW+timedelta(microseconds=3))
 def run(payload):
  with Session(engine) as db:
   try:return originals.execute(db,institute,payload,"manager")
   except HTTPException as error:
    assert error.status_code==400
    return None
 with ThreadPoolExecutor(max_workers=2) as pool:one,two=[f.result(timeout=20) for f in [pool.submit(run,body(audience.id,"same")),pool.submit(run,body(audience.id,"same"))]]
 assert one==two and one is not None
 root=one.revision.campaign_id
 with ThreadPoolExecutor(max_workers=2) as pool:results=[f.result(timeout=20) for f in [pool.submit(run,body(audience.id,key,root,one.revision.id,"review")) for key in ("one","two")]]
 assert sum(r is not None for r in results)==1
 with Session(engine) as db:
  assert originals.current(db,institute,root)==next(r for r in results if r is not None)
  assert originals.require(db,institute,one.revision.id)==one
