import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session
from app.database.base import Base
from app.modules.dev.routes import init_demo_data
from app.modules.employees.models import Employee
from app.modules.workforce import work_intervals
from app.modules.workforce.work_interval_schemas import WorkIntervalCreate
from app.modules.workforce.absence_schemas import AbsenceCancel
from app.modules.workforce.models import EmployeeWorkInterval, WorkIntervalCancellation
from test_source_index_migration_10t import owned_engine
from test_work_intervals_11l import payload


@pytest.mark.parametrize("database", ["sqlite", "postgresql"])
def test_work_interval_migration_roundtrip_and_history_protection(tmp_path, monkeypatch, database):
    with owned_engine(tmp_path, monkeypatch, database) as (engine, config):
        command.upgrade(config, "head")
        with engine.connect() as connection:
            assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
        command.downgrade(config, "6ade31b9204f")
        assert "employee_work_intervals" not in inspect(engine).get_table_names()
        command.upgrade(config, "head")
        with Session(engine) as db:
            init_demo_data(db)
            employee = db.scalar(select(Employee))
            original = work_intervals.create(db, employee.institute_id, WorkIntervalCreate.model_validate(payload(employee.id)), "signed")
            work_intervals.cancel(db, employee.institute_id, original.id, AbsenceCancel(reason="Corrected", idempotency_key="cancel"), "signed")
        def facts():
            with engine.connect() as connection:
                return [[dict(row) for row in connection.execute(select(model)).mappings()] for model in (EmployeeWorkInterval, WorkIntervalCancellation)]
        before = facts()
        with pytest.raises(RuntimeError, match="Recorded work interval history"):
            command.downgrade(config, "6ade31b9204f")
        assert facts() == before
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "ea5b7cd43926"
            assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
