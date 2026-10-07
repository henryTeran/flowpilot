import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import event, inspect, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from app.database.base import Base
from app.modules.dev.routes import init_demo_data
from app.modules.employees.models import Employee
from app.modules.services.models import Service
from app.modules.workforce import commissions as ledger
from app.modules.workforce.absence_schemas import AbsenceCancel
from app.modules.workforce.models import EmployeeCommission, CommissionCancellation
from test_source_index_migration_10t import owned_engine
from test_commissions_11ae import fixture, body


@pytest.mark.parametrize("database", ["sqlite", "postgresql"])
def test_commission_migration_exact_money_ownership_roundtrip_and_protected_history(tmp_path, monkeypatch, database):
    with owned_engine(tmp_path, monkeypatch, database) as (engine, config):
        if database == "sqlite":
            @event.listens_for(engine, "connect")
            def owned_foreign_keys(connection, _record): connection.execute("PRAGMA foreign_keys=ON")
        command.upgrade(config, "head")
        with engine.connect() as connection:
            assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
        command.downgrade(config, "9bc52e18d430")
        assert "employee_commissions" not in inspect(engine).get_table_names()
        command.upgrade(config, "head")
        with Session(engine) as db:
            init_demo_data(db); employee = db.scalar(select(Employee)); service = db.scalar(select(Service.id))
            institute = employee.institute_id
        first, _ = fixture(engine, institute, employee.id, service, monkeypatch)
        with Session(engine) as db:
            original = ledger.create(db, institute, body(first), "manager")
            for changes in [dict(employee_id="foreign"), dict(rule_id="missing"), dict(ticket_id="missing"), dict(line_id="missing"),
                dict(currency="USD"), dict(amount_minor="-1"), dict(amount_minor="1.5"), dict(amount_minor="001"),
                dict(amount_minor="garbage"), dict(amount_minor="10000000000")]:
                with pytest.raises(DBAPIError):
                    with db.begin_nested(): db.execute(update(EmployeeCommission).where(EmployeeCommission.id == original.id).values(**changes))
            cancelled = ledger.cancel(db, institute, original.id, AbsenceCancel(reason="Explicit migration fixture correction", idempotency_key="cancel"), "manager")
            with pytest.raises(DBAPIError):
                with db.begin_nested(): db.execute(update(CommissionCancellation).where(CommissionCancellation.id == cancelled.id).values(institute_id="foreign"))
            with pytest.raises(DBAPIError):
                with db.begin_nested():
                    db.add(CommissionCancellation(**{**cancelled.model_dump(), "id": "duplicate", "idempotency_key": "duplicate"})); db.flush()
        def facts():
            with engine.connect() as connection:
                return [[dict(row) for row in connection.execute(select(model)).mappings()] for model in (EmployeeCommission, CommissionCancellation)]
        before = facts()
        with pytest.raises(RuntimeError, match="Recorded commission history"):
            command.downgrade(config, "9bc52e18d430")
        assert facts() == before
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "fb6c8de54037"
            assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
