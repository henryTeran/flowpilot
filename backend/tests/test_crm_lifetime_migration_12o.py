from alembic.script import ScriptDirectory
import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import event,inspect,select,text,update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from app.database.base import Base
from app.modules.crm import lifetime_originals as lifetime
from app.modules.crm.models import LifetimeHead,LifetimeOriginal
from app.modules.dev.routes import init_demo_data
from app.modules.institutes.models import Institute
from test_crm_billing_12b import seed
from test_crm_lifetime_originals_12o import body
from test_source_index_migration_10t import owned_engine

@pytest.mark.parametrize("database",["sqlite","postgresql"])
def test_lifetime_roundtrip_scope_and_history_protection(tmp_path,monkeypatch,database):
    with owned_engine(tmp_path,monkeypatch,database) as (engine,config):
        if database=="sqlite":
            @event.listens_for(engine,"connect")
            def foreign_keys(connection,record): connection.execute("PRAGMA foreign_keys=ON")
        command.upgrade(config,"head")
        with engine.connect() as connection: assert compare_metadata(MigrationContext.configure(connection),Base.metadata)==[]
        command.downgrade(config,"b72d4e91a603")
        assert "crm_lifetime_originals" not in inspect(engine).get_table_names()
        command.upgrade(config,"head")
        with Session(engine) as db:
            init_demo_data(db); institute=db.scalar(select(Institute.id)); seed(db,institute)
            first=lifetime.create(db,institute,"customer_crm",body(institute),"manager")
            second=lifetime.create(db,institute,"customer_crm",body(institute,key="second",previous=first.id),"manager")
            other=lifetime.create(db,institute,"customer_other",body(institute,customer="customer_other"),"manager")
            with pytest.raises(DBAPIError):
                with db.begin_nested(): db.execute(update(LifetimeHead).where(LifetimeHead.customer_id=="customer_crm").values(original_id=other.id))
            with pytest.raises(DBAPIError):
                with db.begin_nested(): db.execute(update(LifetimeOriginal).where(LifetimeOriginal.id==second.id).values(previous_id=other.id))
        with pytest.raises(RuntimeError,match="Recorded lifetime history"): command.downgrade(config,"b72d4e91a603")
        with Session(engine) as db:
            assert lifetime.current(db,institute,"customer_crm")==second
            assert lifetime.require(db,institute,"customer_crm",first.id)==first
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version"))== ScriptDirectory.from_config(config).get_current_head()
            assert compare_metadata(MigrationContext.configure(connection),Base.metadata)==[]
