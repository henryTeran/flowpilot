import importlib.util
from pathlib import Path
from datetime import timedelta
import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text, select
from sqlalchemy.orm import Session
from app.database.base import Base
from app.modules.base.models import SensitiveOperationOriginal, ApprovalOriginal, ExecutionOriginal
from app.modules.appointments.models import Appointment, BookingEvent
from app.modules.employees.models import Employee
from app.modules.services.models import Service
from app.modules.dev.routes import init_demo_data
from app.modules.institutes.models import Institute
from app.shared.time import utcnow
from test_source_index_migration_10t import owned_engine


def test_execution_offline_downgrade_refuses(monkeypatch):
    path = Path(__file__).parents[1] / "migrations/versions/f562c3a4edf6_base_execution_originals.py"
    spec = importlib.util.spec_from_file_location("execution_migration", path)
    migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
    monkeypatch.setattr(migration.context, "is_offline_mode", lambda: True)
    with pytest.raises(RuntimeError, match="online downgrade"): migration.downgrade()


@pytest.mark.parametrize("database", ["sqlite", "postgresql"])
def test_execution_empty_roundtrip_metadata_and_history_guard(tmp_path, monkeypatch, database):
    with owned_engine(tmp_path, monkeypatch, database) as (engine, config):
        command.upgrade(config, "head")
        with engine.connect() as connection:
            assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
        command.downgrade(config, "e451b293dcf5")
        assert "base_execution_originals" not in inspect(engine).get_table_names()
        command.upgrade(config, "head")
        with Session(engine) as db:
            init_demo_data(db); institute = db.scalar(select(Institute.id)); now = utcnow()
            employee = db.scalar(select(Employee.id).where(Employee.institute_id == institute)); service = db.scalar(select(Service.id))
            db.add(Appointment(id="migration-appointment", institute_id=institute, employee_id=employee, service_id=service,
                customer_name="Test", start_time=now, end_time=now+timedelta(minutes=30), status="cancelled"))
            db.add(SensitiveOperationOriginal(id="operation", institute_id=institute, idempotency_key="operation", actor_id="signed",
                created_at=now, original={}, fingerprint="0"*64)); db.flush()
            db.add(ApprovalOriginal(id="approval", institute_id=institute, operation_id="operation", previous_id=None,
                idempotency_key="approval", actor_id="signed", created_at=now, original={}, fingerprint="0"*64))
            db.add(BookingEvent(id="booking-event", institute_id=institute, appointment_id="migration-appointment", event_type="cancelled",
                actor_id="signed", occurred_at=now, before={}, after={}, price_reference=None)); db.flush()
            db.add(ExecutionOriginal(id="execution", institute_id=institute, operation_id="operation", approval_id="approval",
                booking_event_id="booking-event", idempotency_key="execution", actor_id="signed", created_at=now, original={}, fingerprint="0"*64))
            db.commit()
        with pytest.raises(RuntimeError, match="cannot be removed"): command.downgrade(config, "e451b293dcf5")
        assert "base_execution_originals" in inspect(engine).get_table_names()
        with engine.connect() as connection:
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar() == ScriptDirectory.from_config(config).get_current_head()
