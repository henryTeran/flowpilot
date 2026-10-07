import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import event, inspect, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from app.database.base import Base
from app.modules.crm import policies
from app.modules.crm.models import SegmentPolicyOriginal, SegmentPolicyHead
from app.modules.dev.routes import init_demo_data
from app.modules.institutes.models import Institute
from test_crm_policies_12d import body
from test_source_index_migration_10t import owned_engine


@pytest.mark.parametrize("database", ["sqlite", "postgresql"])
def test_policy_migration_roundtrip_scoped_heads_and_protected_originals(tmp_path, monkeypatch, database):
    with owned_engine(tmp_path, monkeypatch, database) as (engine, config):
        if database == "sqlite":
            @event.listens_for(engine, "connect")
            def foreign_keys(connection, record):
                connection.execute("PRAGMA foreign_keys=ON")
        command.upgrade(config, "head")
        with engine.connect() as connection:
            assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
        command.downgrade(config, "ac61f9d028e5")
        assert "crm_segment_policy_originals" not in inspect(engine).get_table_names()
        command.upgrade(config, "head")
        with Session(engine) as db:
            init_demo_data(db)
            institute = db.scalar(select(Institute.id))
            origin = db.get(Institute, institute)
            db.add(Institute(id="crm_foreign", region_id=origin.region_id, name="Foreign", city="Test"))
            db.commit()
            first = policies.create(db, institute, body(institute), "manager")
            second = policies.create(db, institute, body(institute, "second", first.id), "manager")
            foreign = policies.create(db, "crm_foreign", body("crm_foreign"), "manager")
            with pytest.raises(DBAPIError):
                with db.begin_nested():
                    db.execute(update(SegmentPolicyHead).where(SegmentPolicyHead.institute_id == institute).values(policy_id=foreign.id))
            with pytest.raises(DBAPIError):
                with db.begin_nested():
                    db.execute(update(SegmentPolicyOriginal).where(SegmentPolicyOriginal.id == second.id).values(previous_policy_id=foreign.id))
        with pytest.raises(RuntimeError, match="Recorded CRM policy history"):
            command.downgrade(config, "ac61f9d028e5")
        with Session(engine) as db:
            assert policies.current(db, institute) == second
            assert policies.require(db, institute, first.id) == first
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "3fa0c198447b"
            assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
