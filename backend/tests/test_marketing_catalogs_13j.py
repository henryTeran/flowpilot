import pytest
from sqlalchemy import event
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.marketing import catalogs,templates,campaign_originals
from test_marketing_campaign_originals_13i import exercise as campaign_fixture
from test_marketing_templates_13h import body as template_body
from test_postgres_scheduling_4d import postgres_flow
from test_ticket_workflow import _auth_headers,_bootstrap_reference_data

def exercise(engine,institute,monkeypatch):
 campaign_fixture(engine,institute,monkeypatch)
 with Session(engine) as db:
  for index in range(23):templates.create(db,institute,template_body(f"catalog-{index}"),"manager")
  statements=[]
  def track(conn,cursor,statement,parameters,context,executemany):statements.append(statement)
  event.listen(engine,"before_cursor_execute",track)
  try:first=catalogs.templates_current(db,institute)
  finally:event.remove(engine,"before_cursor_execute",track)
  assert len(statements)==3
  second=catalogs.templates_current(db,institute,20,20)
  assert first.total==second.total==24 and len(first.items)==20 and len(second.items)==4
  assert len({row.template_id for row in first.items+second.items})==24
  assert all(row.institute_id==institute for row in first.items+second.items)
  selected=first.items[0]
  newer=templates.create(db,institute,template_body("catalog-correction",selected.template_id,selected.id),"manager")
  assert next(row for row in catalogs.templates_current(db,institute).items if row.template_id==selected.template_id)==newer
  assert catalogs.templates_current(db,institute,24,20).items==()
  campaigns=catalogs.campaigns_current(db,institute,0,1);other=catalogs.campaigns_current(db,institute,1,1)
  assert campaigns.total==other.total==2 and len(campaigns.items)==len(other.items)==1
  assert {r.revision.state for r in campaigns.items+other.items}=={"DRAFT"}
  audiences=catalogs.audiences(db,institute,0,1);assert audiences.total==2 and len(audiences.items)==1
  assert catalogs.audiences(db,"marketing_foreign").total==0
  assert catalogs.templates_current(db,"marketing_foreign").total==0
  assert catalogs.campaigns_current(db,"marketing_foreign").total==0
  from pydantic import ValidationError
  with pytest.raises(ValidationError):catalogs.Page[templates.Original](institute_id=institute,total=2,offset=0,limit=20,items=())

def test_sqlite_owned_current_catalog_pages_and_signed_roles(client,monkeypatch):
 institute,_,_=_bootstrap_reference_data(client);exercise(main_module.engine,institute,monkeypatch)
 assert client.get("/openapi.json").status_code==200
 headers=_auth_headers("responsable_institut",institute);base=f"/api/v1/marketing/institutes/{institute}"
 for path in ("/templates","/campaigns","/audience-captures"):
  response=client.get(base+path+"?offset=0&limit=1",headers=headers);assert response.status_code==200 and len(response.json()["items"])==1
  assert client.get(base+path+"?limit=51",headers=headers).status_code==422
  assert client.get(base+path+"?offset=-1",headers=headers).status_code==422
  assert client.get(base+path).status_code==403
  for role,owner in [("accueil",institute),("collaboratrice",institute),("responsable_institut","foreign")]:assert client.get(base+path,headers=_auth_headers(role,owner)).status_code==403

def test_postgres_owned_current_catalog_pages(postgres_flow,monkeypatch):exercise(postgres_flow[0],postgres_flow[1],monkeypatch)
