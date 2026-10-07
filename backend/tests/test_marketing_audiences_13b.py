import pytest
from pydantic import ValidationError
from datetime import timedelta
from sqlalchemy.orm import Session
from app.modules.marketing import audiences
from app.modules.crm import policies, lifecycle_originals
from app.modules.customers.models import Customer
from app.modules.institutes.models import Institute
import app.main as main_module
from test_crm_billing_12b import NOW
from test_crm_policies_12d import body as policy_body
from test_crm_lifecycle_originals_12t import body as declaration_body
from test_postgres_scheduling_4d import postgres_flow
from test_ticket_workflow import _auth_headers, _bootstrap_reference_data

def exercise(engine,institute,monkeypatch):
 monkeypatch.setattr(audiences,"utcnow",lambda:NOW);monkeypatch.setattr(policies,"utcnow",lambda:NOW);monkeypatch.setattr(lifecycle_originals,"utcnow",lambda:NOW)
 with Session(engine) as db:
  db.add(Institute(id="marketing_foreign",region_id=db.get(Institute,institute).region_id,name="Foreign",city="Test"));db.flush()
  for index in range(56):
   db.add(Customer(id=f"aud_{index:03}",institute_id=institute if index<55 else "marketing_foreign",display_name="Identical Name",phone=None,search_name="identical name",phone_digits="",idempotency_key=str(index),creation_fingerprint="fixture",created_at=NOW,created_by="actor"))
  db.commit()
  selection=audiences.Selection(segments=("NEW",),channel="email",after=None)
  absent=audiences.read(db,institute,selection);assert len(absent.items)==50 and not any(i.selected_segment for i in absent.items)
  policies.create(db,institute,policy_body(institute),"manager")
  for customer,permission in [("aud_000","granted"),("aud_001","refused")]:
   communications=[{"channel":channel,"purpose":purpose,"permission":permission if channel=="email" and purpose=="marketing" else "unknown","evidence":"Explicit marketing permission" if channel=="email" and purpose=="marketing" else None} for channel in ("email","sms") for purpose in ("service_follow_up","marketing")]
   lifecycle_originals.create(db,institute,customer,declaration_body(institute,customer,communications=communications),"manager")
  followup=[{"channel":channel,"purpose":purpose,"permission":"granted" if channel=="email" and purpose=="service_follow_up" else "unknown","evidence":"Explicit follow-up only" if channel=="email" and purpose=="service_follow_up" else None} for channel in ("email","sms") for purpose in ("service_follow_up","marketing")]
  lifecycle_originals.create(db,institute,"aud_002",declaration_body(institute,"aud_002",communications=followup),"manager")
  first=audiences.read(db,institute,selection);assert len(first.items)==50 and first.next_after=="aud_049"
  assert all(i.selected_segment and i.profile.captured_at==first.captured_at for i in first.items)
  assert first.items[0].eligible_by_recorded_permission and first.items[1].marketing_permission=="refused" and not first.items[1].eligible_by_recorded_permission
  assert not first.items[2].eligible_by_recorded_permission and first.items[2].marketing_permission=="unknown"
  assert audiences.Page.model_validate_json(first.model_dump_json())==first
  for field,value in [("selected_segment",False),("marketing_permission","refused"),("eligible_by_recorded_permission",False),("customer_id","foreign")]:
   raw=first.model_dump();raw["items"][0][field]=value
   with pytest.raises(ValidationError):audiences.Page.model_validate(raw)
  raw=first.model_dump();raw["next_after"]="forged"
  with pytest.raises(ValidationError):audiences.Page.model_validate(raw)
  raw=first.model_dump();raw["items"]=tuple(reversed(raw["items"]))
  with pytest.raises(ValidationError):audiences.Page.model_validate(raw)
  raw=first.model_dump();raw["items"][0]["profile"]["captured_at"]=NOW+timedelta(microseconds=1)
  with pytest.raises(ValidationError):audiences.Page.model_validate(raw)
  raw=first.model_dump();raw["items"][0]["declaration"]["declaration"]["customer_id"]="foreign"
  with pytest.raises(ValidationError):audiences.Page.model_validate(raw)
  raw=first.model_dump();raw["items"][0]["profile"]["segment"]["state"]="VIP"
  with pytest.raises(ValidationError):audiences.Page.model_validate(raw)
  assert not first.delivery_authorized and not first.complete_institute_audience
  second=audiences.read(db,institute,selection.model_copy(update={"after":first.next_after}));assert len(second.items)==5 and second.next_after is None
  assert [i.customer_id for i in first.items+second.items]==[f"aud_{i:03}" for i in range(55)]
  sms=audiences.read(db,institute,selection.model_copy(update={"channel":"sms"}));assert not any(i.eligible_by_recorded_permission for i in sms.items)
  push=audiences.read(db,institute,selection.model_copy(update={"channel":"push"}));assert all(i.marketing_permission=="unsupported_channel" and not i.eligible_by_recorded_permission for i in push.items)
  original=first.items[0].declaration
  monkeypatch.setattr(lifecycle_originals,"utcnow",lambda:NOW+timedelta(microseconds=1))
  lifecycle_originals.create(db,institute,"aud_000",declaration_body(institute,"aud_000",key="future",previous=original.id,communications=[p.model_dump() for p in original.declaration.communications]),"manager")
  future=audiences.read(db,institute,selection);assert future.items[0].marketing_permission=="future_declaration" and not future.items[0].eligible_by_recorded_permission
  return first

def test_sqlite_bounded_owned_segments_permissions_and_signed_http(client,monkeypatch):
 institute,_,_=_bootstrap_reference_data(client);exercise(main_module.engine,institute,monkeypatch)
 path=f"/api/v1/marketing/institutes/{institute}/audience-observations";payload={"segments":["NEW"],"channel":"email","after":None}
 reply=client.post(path,json=payload,headers=_auth_headers("responsable_institut",institute));assert reply.status_code==200 and len(reply.json()["items"])==50
 for role,owner in [("accueil",institute),("collaboratrice",institute),("responsable_institut","foreign")]:assert client.post(path,json=payload,headers=_auth_headers(role,owner)).status_code==403
 assert client.post(path,json=payload).status_code==403
 assert client.post(path,json={**payload,"segments":[]},headers=_auth_headers("responsable_institut",institute)).status_code==422
 assert client.post(path,json={**payload,"segments":["NEW","NEW"]},headers=_auth_headers("responsable_institut",institute)).status_code==422

def test_postgres_bounded_owned_segments_and_separate_permissions(postgres_flow,monkeypatch):exercise(postgres_flow[0],postgres_flow[1],monkeypatch)
