import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import event, inspect, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from app.database.base import Base
from app.modules.crm.models import EventCaptureOriginal, EventRevision, EventHead
from app.modules.dev.routes import init_demo_data
from app.modules.institutes.models import Institute
from test_crm_billing_12b import seed, NOW
from test_source_index_migration_10t import owned_engine

@pytest.mark.parametrize("database", ["sqlite", "postgresql"])
def test_event_ledger_roundtrip_scope_constraints_and_protected_history(tmp_path,monkeypatch,database):
    with owned_engine(tmp_path,monkeypatch,database) as (engine,config):
        if database=="sqlite":
            @event.listens_for(engine,"connect")
            def foreign_keys(connection,record):connection.execute("PRAGMA foreign_keys=ON")
        command.upgrade(config,"head")
        with engine.connect() as connection:assert compare_metadata(MigrationContext.configure(connection),Base.metadata)==[]
        command.downgrade(config,"ea5b7cd43926")
        assert "crm_event_revisions" not in inspect(engine).get_table_names()
        command.upgrade(config,"head")
        with Session(engine) as db:
            init_demo_data(db);institute=db.scalar(select(Institute.id));seed(db,institute)
            for customer in ("customer_crm","customer_other"):
                db.add(EventCaptureOriginal(id=customer,institute_id=institute,customer_id=customer,idempotency_key="capture",actor_id="manager",reason="Schema fixture",captured_at=NOW,source={"schema_fixture":True}))
            db.flush()
            for customer in ("customer_crm","customer_other"):
                db.add(EventRevision(id=customer,institute_id=institute,customer_id=customer,event_key="event",capture_id=customer,previous_id=None,decision={"schema_fixture":True}))
            db.flush()
            db.add(EventHead(institute_id=institute,customer_id="customer_crm",event_key="event",revision_id="customer_crm"));db.commit()
            for statement in (
                update(EventHead).values(revision_id="customer_other"),
                update(EventRevision).where(EventRevision.id=="customer_crm").values(capture_id="customer_other"),
                update(EventRevision).where(EventRevision.id=="customer_crm").values(previous_id="customer_other")):
                with pytest.raises(DBAPIError):
                    with db.begin_nested():db.execute(statement)
        with pytest.raises(RuntimeError,match="Recorded event history"):command.downgrade(config,"ea5b7cd43926")
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version"))=="1d8eaf762259"
            assert connection.scalar(text("SELECT COUNT(*) FROM crm_event_revisions"))==2
            assert compare_metadata(MigrationContext.configure(connection),Base.metadata)==[]
