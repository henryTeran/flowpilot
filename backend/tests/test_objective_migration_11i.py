import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session
from app.database.base import Base
from app.modules.dev.routes import init_demo_data
from app.modules.employees.models import Employee
from app.modules.workforce import objectives
from app.modules.workforce.objective_schemas import ObjectiveCreate, ObjectiveCancel
from app.modules.workforce.models import EmployeeObjective, ObjectiveCancellation
from test_source_index_migration_10t import owned_engine
from test_workforce_objectives_11i import payload


@pytest.mark.parametrize("database", ["sqlite", "postgresql"])
def test_objective_migration_empty_roundtrip_and_cancelled_history_guard(tmp_path, monkeypatch, database):
    with owned_engine(tmp_path, monkeypatch, database) as (engine, config):
        command.upgrade(config, "head")
        with engine.connect() as connection:
            assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
        command.downgrade(config, "5fcb2a07193e")
        assert "employee_objectives" not in inspect(engine).get_table_names()
        command.upgrade(config, "head")
        with Session(engine) as db:
            init_demo_data(db)
            employee = db.scalar(select(Employee))
            original = objectives.create(db, employee.institute_id, ObjectiveCreate.model_validate(payload(employee.id)), "signed")
            objectives.cancel(db, employee.institute_id, original.id, ObjectiveCancel(reason="Corrected target", idempotency_key="cancel"), "signed")
        def facts():
            with engine.connect() as connection:
                return [[dict(row) for row in connection.execute(select(model)).mappings()] for model in (EmployeeObjective, ObjectiveCancellation)]
        before = facts()
        with pytest.raises(RuntimeError, match="Recorded objective history"):
            command.downgrade(config, "5fcb2a07193e")
        assert facts() == before
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "8af04d719b32"
            assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
