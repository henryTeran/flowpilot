from datetime import timedelta

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from app.database.base import Base
from app.modules.dev.routes import init_demo_data
from app.modules.employees.models import Employee
from app.modules.workforce import absences
from app.modules.workforce.absence_schemas import AbsenceCreate, AbsenceCancel
from app.modules.workforce.models import EmployeeAbsence, AbsenceCancellation
from app.shared.time import utcnow
from test_source_index_migration_10t import owned_engine


@pytest.mark.parametrize("database", ["sqlite", "postgresql"])
def test_absence_migration_empty_roundtrip_and_cancelled_history_guard(tmp_path, monkeypatch, database):
    with owned_engine(tmp_path, monkeypatch, database) as (engine, config):
        command.upgrade(config, "head")
        with engine.connect() as connection:
            assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
        command.downgrade(config, "2c897df4e6fb")
        assert "employee_absences" not in inspect(engine).get_table_names()
        command.upgrade(config, "head")
        with Session(engine) as db:
            init_demo_data(db)
            employee = db.scalar(select(Employee))
            start = utcnow() + timedelta(days=1)
            original = absences.create(db, employee.institute_id, AbsenceCreate(
                employee_id=employee.id, kind="leave", start_time=start,
                end_time=start + timedelta(hours=1), reason="Owned fixture", idempotency_key="original"), "signed")
            absences.cancel(db, employee.institute_id, original.id,
                AbsenceCancel(reason="Return", idempotency_key="cancel"), "signed")
        def records():
            with engine.connect() as connection:
                return [[dict(row) for row in connection.execute(select(model)).mappings()]
                        for model in (EmployeeAbsence, AbsenceCancellation)]
        before = records()
        with pytest.raises(RuntimeError, match="Recorded workforce history"):
            command.downgrade(config, "2c897df4e6fb")
        assert records() == before
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "c83e5fa21704"
            assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
