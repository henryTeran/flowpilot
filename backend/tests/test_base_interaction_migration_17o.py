import importlib.util
from pathlib import Path
import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import inspect
from sqlalchemy.orm import Session
from app.database.base import Base
from app.modules.base.models import InteractionOriginal
from app.modules.dev.routes import init_demo_data
from app.shared.time import utcnow
from test_source_index_migration_10t import owned_engine

def test_interaction_offline_downgrade_refuses(monkeypatch):
    path = Path(__file__).parents[1] / "migrations/versions/0673d4b5f0a7_base_interaction_originals.py"
    spec = importlib.util.spec_from_file_location("interaction_migration", path)
    migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
    monkeypatch.setattr(migration.context, "is_offline_mode", lambda: True)
    with pytest.raises(RuntimeError, match="online downgrade"): migration.downgrade()

@pytest.mark.parametrize("database", ["sqlite", "postgresql"])
def test_interaction_roundtrip_metadata_and_populated_guard(tmp_path, monkeypatch, database):
    with owned_engine(tmp_path, monkeypatch, database) as (engine, config):
        command.upgrade(config, "head")
        with engine.connect() as connection: assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
        command.downgrade(config, "f562c3a4edf6")
        assert "base_interaction_originals" not in inspect(engine).get_table_names()
        command.upgrade(config, "head")
        with Session(engine) as db:
            init_demo_data(db)
            from app.modules.institutes.models import Institute
            institute = db.query(Institute).first().id
            db.add(InteractionOriginal(id="guard-fixture", institute_id=institute, sequence=1, previous_id=None, attempt_id=None,
                actor_id="manager", created_at=utcnow(), original={}, fingerprint="0"*64)); db.commit()
        with pytest.raises(RuntimeError, match="cannot be removed"): command.downgrade(config, "f562c3a4edf6")
        assert "base_interaction_originals" in inspect(engine).get_table_names()
