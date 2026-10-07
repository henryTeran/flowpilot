import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import event, inspect, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from app.database.base import Base
from app.modules.marketing.models import AudienceOriginal,AudiencePage
from app.modules.dev.routes import init_demo_data
from app.modules.institutes.models import Institute
from test_source_index_migration_10t import owned_engine
from test_crm_billing_12b import NOW
@pytest.mark.parametrize("database",["sqlite","postgresql"])
def test_marketing_audience_schema_roundtrip_scope_replay_and_protected_history(tmp_path,monkeypatch,database):
 with owned_engine(tmp_path,monkeypatch,database) as (engine,config):
  if database=="sqlite":
   @event.listens_for(engine,"connect")
   def foreign_keys(connection,record):connection.execute("PRAGMA foreign_keys=ON")
  command.upgrade(config,"head")
  with engine.connect() as connection:assert compare_metadata(MigrationContext.configure(connection),Base.metadata)==[]
  command.downgrade(config,"fb6c8de54037");assert "marketing_audience_originals" not in inspect(engine).get_table_names()
  command.upgrade(config,"head")
  with Session(engine) as db:
   init_demo_data(db);institute=db.scalar(select(Institute.id));db.add(Institute(id="foreign_audience",region_id=db.get(Institute,institute).region_id,name="Foreign",city="Test"));db.flush()
   db.add(AudienceOriginal(id="capture",institute_id=institute,actor_id="manager",reason="Schema fixture",idempotency_key="key",captured_at=NOW,request={"schema_fixture":True},summary={"schema_fixture":True}));db.flush()
   db.add(AudiencePage(institute_id=institute,capture_id="capture",page_index=0,observation={"schema_fixture":True}));db.commit()
   for row in [AudiencePage(institute_id="foreign_audience",capture_id="capture",page_index=1,observation={}),AudiencePage(institute_id=institute,capture_id="capture",page_index=-1,observation={}),AudienceOriginal(id="duplicate",institute_id=institute,actor_id="manager",reason="Schema fixture",idempotency_key="key",captured_at=NOW,request={},summary={})]:
    db.add(row)
    with pytest.raises(DBAPIError):db.commit()
    db.rollback()
  with pytest.raises(RuntimeError,match="history cannot be removed"):command.downgrade(config,"fb6c8de54037")
  assert "marketing_audience_pages" in inspect(engine).get_table_names()
