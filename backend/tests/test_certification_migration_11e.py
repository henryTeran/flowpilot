import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session
from app.database.base import Base
from app.modules.dev.routes import init_demo_data
from app.modules.employees.models import Employee
from app.modules.workforce import certifications
from app.modules.workforce.certification_schemas import CertificationCreate, CertificationRevoke
from app.modules.workforce.models import EmployeeCertification, CertificationRevocation
from test_source_index_migration_10t import owned_engine
from test_workforce_certifications_11e import payload


@pytest.mark.parametrize("database", ["sqlite", "postgresql"])
def test_original_certification_migration_empty_roundtrip_and_revoked_history_guard(tmp_path, monkeypatch, database):
    with owned_engine(tmp_path, monkeypatch, database) as (engine, config):
        command.upgrade(config, "head")
        with engine.connect() as connection:
            assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
        command.downgrade(config, "3da908e5f70c")
        assert "employee_certifications" not in inspect(engine).get_table_names()
        command.upgrade(config, "head")
        with Session(engine) as db:
            init_demo_data(db)
            employee = db.scalar(select(Employee))
            body = CertificationCreate.model_validate(payload(employee.id))
            original = certifications.create(db, employee.institute_id, body, "signed")
            certifications.revoke(db, employee.institute_id, original.id,
                CertificationRevoke(reason="Original correction", idempotency_key="revoke"), "signed")
        def records():
            with engine.connect() as connection:
                return [[dict(row) for row in connection.execute(select(model)).mappings()]
                        for model in (EmployeeCertification, CertificationRevocation)]
        before = records()
        with pytest.raises(RuntimeError, match="Recorded certification history"):
            command.downgrade(config, "3da908e5f70c")
        assert records() == before
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "6ade31b9204f"
            assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
