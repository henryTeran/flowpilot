import importlib.util
from pathlib import Path
import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text, select
from sqlalchemy.orm import Session
from app.database.base import Base
from app.modules.dev.routes import init_demo_data
from app.modules.institutes.models import Institute
from test_source_index_migration_10t import owned_engine


def test_closure_original_offline_downgrade_refuses(monkeypatch):
    path = Path(__file__).parents[1] / "migrations/versions/8ef5b643992a_closure_valuation_originals.py"
    spec = importlib.util.spec_from_file_location("closure_migration", path)
    migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
    monkeypatch.setattr(migration.context, "is_offline_mode", lambda: True)
    with pytest.raises(RuntimeError, match="online downgrade"): migration.downgrade()


@pytest.mark.parametrize("database", ["sqlite", "postgresql"])
def test_closure_original_schema_history_guard(tmp_path, monkeypatch, database):
    with owned_engine(tmp_path, monkeypatch, database) as (engine, config):
        command.upgrade(config, "head")
        with engine.connect() as connection:
            assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
        command.downgrade(config, "7de4a532881f")
        assert "revenue_closure_valuation_originals" not in inspect(engine).get_table_names()
        command.upgrade(config, "head")
        with Session(engine) as db:
            init_demo_data(db); institute = db.scalar(select(Institute.id))
        with engine.begin() as connection:
            connection.execute(text("INSERT INTO revenue_closure_valuation_originals (id, institute_id, appointment_id, idempotency_key, actor_id, created_at, original, fingerprint) VALUES (:id,:institute,:appointment,:key,:actor,:at,:original,:hash)"),
                dict(id="retained", institute=institute, appointment="captured-booking", key="migration-key", actor="signed", at="2026-10-07T12:00:00+00:00", original="{}", hash="0"*64))
        with pytest.raises(RuntimeError, match="cannot be removed"): command.downgrade(config, "7de4a532881f")
        assert "revenue_closure_valuation_originals" in inspect(engine).get_table_names()
