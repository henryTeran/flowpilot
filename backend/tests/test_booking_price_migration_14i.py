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
from app.modules.employees.models import Employee
from app.modules.services.models import Service
from app.modules.appointments.models import Appointment, BookingEvent
from test_source_index_migration_10t import owned_engine
from test_revenue_billing_14a import NOW


def test_price_reference_offline_downgrade_refuses(monkeypatch):
    path = Path(__file__).parents[1] / "migrations/versions/6cd3f421770e_booking_price_references.py"
    spec = importlib.util.spec_from_file_location("price_migration", path)
    migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
    monkeypatch.setattr(migration.context, "is_offline_mode", lambda: True)
    with pytest.raises(RuntimeError, match="online downgrade"): migration.downgrade()


@pytest.mark.parametrize("database", ["sqlite", "postgresql"])
def test_price_reference_owned_schema_and_preserved_history(tmp_path, monkeypatch, database):
    with owned_engine(tmp_path, monkeypatch, database) as (engine, config):
        command.upgrade(config, "head")
        with engine.connect() as connection:
            assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
        command.downgrade(config, "5bc2e310669d")
        assert "price_reference" not in {column["name"] for column in inspect(engine).get_columns("booking_events")}
        command.upgrade(config, "head")
        with Session(engine) as db:
            init_demo_data(db); institute = db.scalar(select(Institute.id))
            employee = db.scalar(select(Employee.id).where(Employee.institute_id == institute)); service = db.scalar(select(Service.id))
            db.add(Appointment(id="legacy-price", institute_id=institute, employee_id=employee, service_id=service,
                customer_name="Legacy", start_time=NOW, end_time=NOW, status="cancelled"))
            db.flush()
            db.add(BookingEvent(id="legacy-price-event", institute_id=institute, appointment_id="legacy-price", event_type="created",
                occurred_at=NOW, before=None, after={}, price_reference=None)); db.commit()
        command.downgrade(config, "5bc2e310669d"); command.upgrade(config, "head")
        with engine.begin() as connection:
            connection.execute(text("UPDATE booking_events SET price_reference = :value WHERE id = 'legacy-price-event'"), {"value": '{"retained":true}'})
        with pytest.raises(RuntimeError, match="cannot be removed"): command.downgrade(config, "5bc2e310669d")
