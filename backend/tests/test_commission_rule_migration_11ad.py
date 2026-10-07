import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import event, inspect, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.database.base import Base
from app.modules.dev.routes import init_demo_data
from app.modules.employees.models import Employee
from app.modules.workforce import commission_rules as rules
from app.modules.workforce.commission_rule_schemas import CommissionRuleCreate, CommissionRuleCancel
from app.modules.workforce.models import EmployeeCommissionRule, CommissionRuleCancellation
from test_source_index_migration_10t import owned_engine
from test_commission_rules_11ad import payload


@pytest.mark.parametrize("database", ["sqlite", "postgresql"])
def test_rule_migration_parity_roundtrip_constraints_and_history_guard(tmp_path, monkeypatch, database):
    with owned_engine(tmp_path, monkeypatch, database) as (engine, config):
        if database == "sqlite":
            @event.listens_for(engine, "connect")
            def enforce_owned_fixture_foreign_keys(connection, _record):
                connection.execute("PRAGMA foreign_keys=ON")
        command.upgrade(config, "head")
        with engine.connect() as connection:
            assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
        command.downgrade(config, "8af04d719b32")
        assert "employee_commission_rules" not in inspect(engine).get_table_names()
        command.upgrade(config, "head")
        with Session(engine) as db:
            init_demo_data(db); employee = db.scalar(select(Employee))
            original = rules.create(db, employee.institute_id, CommissionRuleCreate.model_validate(payload(employee.id)), "signed")
            for changes in [dict(rate_basis_points=-1), dict(rate_basis_points=10001), dict(rounding="implicit"),
                dict(currency="USD"), dict(category=" "), dict(employee_id="foreign"), dict(service_id="missing"),
                dict(period_end=original.period_start)]:
                with pytest.raises(IntegrityError):
                    with db.begin_nested(): db.execute(update(EmployeeCommissionRule).where(EmployeeCommissionRule.id == original.id).values(**changes))
            cancelled = rules.cancel(db, employee.institute_id, original.id, CommissionRuleCancel(reason="Original correction", idempotency_key="cancel"), "signed")
            with pytest.raises(IntegrityError):
                with db.begin_nested(): db.execute(update(CommissionRuleCancellation).where(CommissionRuleCancellation.id == cancelled.id).values(institute_id="foreign"))
            with pytest.raises(IntegrityError):
                with db.begin_nested():
                    db.add(CommissionRuleCancellation(**{**cancelled.model_dump(), "id": "duplicate-cancel", "idempotency_key": "duplicate-cancel"})); db.flush()
        def facts():
            with engine.connect() as connection:
                return [[dict(row) for row in connection.execute(select(model)).mappings()] for model in (EmployeeCommissionRule, CommissionRuleCancellation)]
        before = facts()
        with pytest.raises(RuntimeError, match="Recorded commission rule history"):
            command.downgrade(config, "8af04d719b32")
        assert facts() == before
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "ea5b7cd43926"
            assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
