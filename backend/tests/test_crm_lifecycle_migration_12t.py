import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import event,inspect,select,text,update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from app.database.base import Base
from app.modules.crm import lifecycle_originals as lifecycle,calendar_policies as calendar
from app.modules.crm.models import LifecycleHead,LifecycleOriginal,BirthdayPolicyHead,BirthdayPolicyOriginal
from app.modules.dev.routes import init_demo_data
from app.modules.institutes.models import Institute
from test_crm_billing_12b import seed
from test_crm_lifecycle_originals_12t import body,policy
from test_source_index_migration_10t import owned_engine

@pytest.mark.parametrize("database",["sqlite","postgresql"])
def test_lifecycle_calendar_roundtrip_scoped_originals_and_protected_history(tmp_path,monkeypatch,database):
    with owned_engine(tmp_path,monkeypatch,database) as (engine,config):
        if database=="sqlite":
            @event.listens_for(engine,"connect")
            def foreign_keys(connection,record): connection.execute("PRAGMA foreign_keys=ON")
        command.upgrade(config,"head")
        with engine.connect() as connection: assert compare_metadata(MigrationContext.configure(connection),Base.metadata)==[]
        command.downgrade(config,"c83e5fa21704")
        assert "crm_lifecycle_originals" not in inspect(engine).get_table_names()
        assert "crm_birthday_policy_originals" not in inspect(engine).get_table_names()
        command.upgrade(config,"head")
        with Session(engine) as db:
            init_demo_data(db);institute=db.scalar(select(Institute.id));seed(db,institute)
            first=lifecycle.create(db,institute,"customer_crm",body(institute),"manager")
            second=lifecycle.create(db,institute,"customer_crm",body(institute,key="second",previous=first.id),"manager")
            other=lifecycle.create(db,institute,"customer_other",body(institute,customer="customer_other"),"manager")
            cal=calendar.create(db,institute,policy(institute),"manager")
            corrected=calendar.create(db,institute,policy(institute,"correction",cal.id),"manager")
            foreign=calendar.create(db,"crm_foreign",policy("crm_foreign"),"manager")
            for statement in (update(LifecycleHead).where(LifecycleHead.customer_id=="customer_crm").values(original_id=other.id),
                update(LifecycleOriginal).where(LifecycleOriginal.id==second.id).values(previous_id=other.id),
                update(BirthdayPolicyHead).where(BirthdayPolicyHead.institute_id==institute).values(policy_id=foreign.id),
                update(BirthdayPolicyOriginal).where(BirthdayPolicyOriginal.id==corrected.id).values(previous_policy_id=foreign.id)):
                with pytest.raises(DBAPIError):
                    with db.begin_nested(): db.execute(statement)
        with pytest.raises(RuntimeError,match="Recorded lifecycle/calendar history"): command.downgrade(config,"c83e5fa21704")
        with Session(engine) as db:
            assert lifecycle.current(db,institute,"customer_crm")==second
            assert lifecycle.require(db,institute,"customer_crm",first.id)==first
            assert calendar.current(db,institute)==corrected
            assert calendar.require(db,institute,cal.id)==cal
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version"))=="1d8eaf762259"
            assert compare_metadata(MigrationContext.configure(connection),Base.metadata)==[]
