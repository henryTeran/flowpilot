import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session
from app.database.base import Base
from app.modules.dev.routes import init_demo_data
from app.modules.employees.models import Employee
from app.modules.resources.repository import skill_facts
from app.modules.workforce.skill_changes import create, SkillChangeCreate
from app.modules.workforce.models import EmployeeSkillChange
from test_source_index_migration_10t import owned_engine


@pytest.mark.parametrize("database", ["sqlite", "postgresql"])
def test_skill_change_migration_original_history_guard(tmp_path, monkeypatch, database):
    with owned_engine(tmp_path, monkeypatch, database) as (engine, config):
        command.upgrade(config, "head")
        with engine.connect() as connection:
            assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
        command.downgrade(config, "4eba19f6082d")
        assert "employee_skill_changes" not in inspect(engine).get_table_names()
        command.upgrade(config, "head")
        with Session(engine) as db:
            init_demo_data(db)
            employee = db.scalar(select(Employee))
            before = sorted(skill_facts(db, employee.institute_id, [employee.id])[employee.id])
            create(db, employee.institute_id, SkillChangeCreate(employee_id=employee.id, expected_skills=before,
                   skills=[*before, "NEW"], reason="Declared", idempotency_key="original"), "signed")
        def records():
            with engine.connect() as connection:
                return [dict(row) for row in connection.execute(select(EmployeeSkillChange)).mappings()]
        original = records()
        with pytest.raises(RuntimeError, match="Recorded skill change history"):
            command.downgrade(config, "4eba19f6082d")
        assert records() == original
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "b72d4e91a603"
            assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
