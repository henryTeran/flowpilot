from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, text

from app.core.config import settings
from app.database.base import Base


def test_queue_migration_preserves_legacy_ticket_and_matches_models(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'migration.db'}"
    monkeypatch.setattr(settings, "DATABASE_URL", url)
    backend = Path(__file__).resolve().parents[1]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "migrations"))
    command.upgrade(config, "3ba965fb2922")
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO companies (id, name, status) VALUES ('co', 'Co', 'active')"))
        conn.execute(text("INSERT INTO countries (id, company_id, code, name) VALUES ('c', 'co', 'CH', 'CH')"))
        conn.execute(text("INSERT INTO regions (id, country_id, name) VALUES ('r', 'c', 'Region')"))
        conn.execute(text("INSERT INTO institutes (id, region_id, name, city, timezone, status) VALUES ('i', 'r', 'Institut', 'City', 'Europe/Zurich', 'active')"))
        conn.execute(text("INSERT INTO queue_tickets (id, institute_id, ticket_number, status, arrival_time) VALUES ('legacy', 'i', 'T-001', 'waiting', '2026-10-02 09:00:00')"))
    command.upgrade(config, "head")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT status, assigned_at, cancelled_at, creation_fingerprint FROM queue_tickets WHERE id='legacy'")).one() == ("waiting", None, None, None)
        assert compare_metadata(MigrationContext.configure(conn), Base.metadata) == []
    command.downgrade(config, "3ba965fb2922")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT status FROM queue_tickets WHERE id='legacy'")).scalar_one() == "waiting"
    command.upgrade(config, "head")
    engine.dispose()
