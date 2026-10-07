from alembic.script import ScriptDirectory
import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import event, inspect, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from app.database.base import Base
from app.modules.crm import automation_originals as policies
from app.modules.crm.models import AutomationPolicyHead, AutomationPolicyOriginal
from app.modules.dev.routes import init_demo_data
from app.modules.institutes.models import Institute
from test_crm_billing_12b import seed
from test_crm_automation_originals_12aa import body
from test_source_index_migration_10t import owned_engine

@pytest.mark.parametrize("database", ["sqlite", "postgresql"])
def test_automation_roundtrip_scoped_heads_predecessors_and_protected_history(tmp_path, monkeypatch, database):
    with owned_engine(tmp_path, monkeypatch, database) as (engine, config):
        if database == "sqlite":
            @event.listens_for(engine, "connect")
            def foreign_keys(connection, record): connection.execute("PRAGMA foreign_keys=ON")
        command.upgrade(config, "head")
        with engine.connect() as connection:
            assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
        command.downgrade(config, "d94f6ab32815")
        assert "crm_automation_policy_originals" not in inspect(engine).get_table_names()
        command.upgrade(config, "head")
        with Session(engine) as db:
            init_demo_data(db); institute = db.scalar(select(Institute.id)); seed(db, institute)
            first = policies.create(db, institute, body(institute), "manager")
            second = policies.create(db, institute, body(institute, "correction", first.id), "manager")
            other = policies.create(db, "crm_foreign", body("crm_foreign"), "manager")
            for statement in (
                update(AutomationPolicyHead).where(AutomationPolicyHead.institute_id == institute).values(policy_id=other.id),
                update(AutomationPolicyOriginal).where(AutomationPolicyOriginal.id == second.id).values(previous_policy_id=other.id)):
                with pytest.raises(DBAPIError):
                    with db.begin_nested(): db.execute(statement)
        with pytest.raises(RuntimeError, match="Recorded automation policy history"):
            command.downgrade(config, "d94f6ab32815")
        with Session(engine) as db:
            assert policies.current(db, institute) == second
            assert policies.require(db, institute, first.id) == first
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == ScriptDirectory.from_config(config).get_current_head()
            assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
