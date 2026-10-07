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
from app.modules.tickets.models import QueueTicket, QueueEvent
from test_source_index_migration_10t import owned_engine
from test_revenue_billing_14a import NOW


def test_offline_downgrade_refuses_unverified_history(monkeypatch):
    path = Path(__file__).parents[1] / "migrations/versions/5bc2e310669d_ticket_cancellation_terms.py"
    spec = importlib.util.spec_from_file_location("cancel_migration", path)
    migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
    monkeypatch.setattr(migration.context, "is_offline_mode", lambda: True)
    with pytest.raises(RuntimeError, match="online downgrade"): migration.downgrade()


@pytest.mark.parametrize("database", ["sqlite", "postgresql"])
def test_owned_migration_empty_reversal_and_snapshot_preservation(tmp_path, monkeypatch, database):
    with owned_engine(tmp_path, monkeypatch, database) as (engine, config):
        command.upgrade(config, "head")
        with engine.connect() as connection:
            assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
        command.downgrade(config, "4ab1d209558c")
        assert "cancellation_terms" not in {column["name"] for column in inspect(engine).get_columns("queue_events")}
        command.upgrade(config, "head")
        with Session(engine) as db:
            init_demo_data(db); institute = db.scalar(select(Institute.id))
            db.add(QueueTicket(id="legacy-cancel", institute_id=institute, ticket_number="legacy", status="cancelled", arrival_time=NOW))
            db.flush()
            db.add(QueueEvent(institute_id=institute, ticket_id="legacy-cancel", event_type="queue.cancelled",
                previous_status="waiting", status="cancelled", occurred_at=NOW, cancellation_terms=None))
            db.commit()
        # None must be SQL NULL, not JSON null, so legacy facts do not prevent
        # removal of an entirely unused snapshot column.
        command.downgrade(config, "4ab1d209558c"); command.upgrade(config, "head")
        with engine.begin() as connection:
            connection.execute(text("UPDATE queue_events SET cancellation_terms = :value WHERE ticket_id = 'legacy-cancel'"), {"value": '{"retained":true}'})
        with pytest.raises(RuntimeError, match="cannot be removed"): command.downgrade(config, "4ab1d209558c")
