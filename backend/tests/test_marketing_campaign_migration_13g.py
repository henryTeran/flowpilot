import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import event,inspect,select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from app.database.base import Base
from app.modules.marketing.models import AudienceOriginal,TemplateOriginal,TemplateHead,CampaignOriginal,CampaignHead
from app.modules.dev.routes import init_demo_data
from app.modules.institutes.models import Institute
from test_source_index_migration_10t import owned_engine
from test_crm_billing_12b import NOW
@pytest.mark.parametrize("database",["sqlite","postgresql"])
def test_campaign_template_schema_scoped_heads_predecessors_sources_and_history(tmp_path,monkeypatch,database):
 with owned_engine(tmp_path,monkeypatch,database) as (engine,config):
  if database=="sqlite":
   @event.listens_for(engine,"connect")
   def foreign_keys(connection,record):connection.execute("PRAGMA foreign_keys=ON")
  command.upgrade(config,"head")
  with engine.connect() as connection:assert compare_metadata(MigrationContext.configure(connection),Base.metadata)==[]
  command.downgrade(config,"0c7d9ef65148");assert "marketing_campaign_originals" not in inspect(engine).get_table_names()
  command.upgrade(config,"head")
  with Session(engine) as db:
   init_demo_data(db);institute=db.scalar(select(Institute.id));foreign="marketing_schema_foreign";db.add(Institute(id=foreign,region_id=db.get(Institute,institute).region_id,name="Foreign",city="Test"));db.flush()
   for identity,owner in [("audience",institute),("foreign_audience",foreign)]:db.add(AudienceOriginal(id=identity,institute_id=owner,actor_id="manager",reason="Schema fixture",idempotency_key=identity,captured_at=NOW,request={"schema_fixture":True},summary={"schema_fixture":True}))
   def template(identity,owner=institute,root="template",previous=None,key=None):return TemplateOriginal(id=identity,institute_id=owner,template_id=root,previous_id=previous,actor_id="manager",reason="Schema fixture",idempotency_key=key or identity,created_at=NOW,request={},content={"schema_fixture":True})
   db.add_all([template("t"),template("other_t",root="other"),template("foreign_t",owner=foreign)]);db.flush()
   def campaign(identity,owner=institute,root="campaign",previous=None,audience="audience",template_id="t",key=None):return CampaignOriginal(id=identity,institute_id=owner,campaign_id=root,previous_id=previous,audience_id=audience,template_original_id=template_id,actor_id="manager",reason="Schema fixture",idempotency_key=key or identity,created_at=NOW,request={},revision={"schema_fixture":True})
   db.add_all([campaign("c"),campaign("other_c",root="other")]);db.flush()
   db.add_all([TemplateHead(institute_id=institute,template_id="template",original_id="t"),CampaignHead(institute_id=institute,campaign_id="campaign",original_id="c")]);db.commit()
   invalid=[template("wrong_previous",previous="other_t"),template("duplicate_template_key",key="t"),campaign("wrong_campaign_previous",previous="other_c"),campaign("foreign_template",template_id="foreign_t"),campaign("foreign_capture",audience="foreign_audience"),campaign("duplicate_campaign_key",key="c"),TemplateHead(institute_id=institute,template_id="wrong",original_id="t"),CampaignHead(institute_id=institute,campaign_id="wrong",original_id="c")]
   for row in invalid:
    db.add(row)
    with pytest.raises(DBAPIError):db.commit()
    db.rollback()
   assert db.get(CampaignHead,(institute,"campaign")).original_id=="c"
  with pytest.raises(RuntimeError,match="history cannot be removed"):command.downgrade(config,"0c7d9ef65148")
  assert "marketing_campaign_heads" in inspect(engine).get_table_names()
