import pytest
from datetime import datetime, timedelta, timezone
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.database.base import Base
from app.modules.dev.routes import init_demo_data
from app.modules.employees.models import Employee
from app.modules.services.models import Service
from app.modules.appointments.models import Appointment
from app.modules.workforce.models import EmployeeRebooking, RebookingCancellation
from test_source_index_migration_10t import owned_engine


@pytest.mark.parametrize("database", ["sqlite", "postgresql"])
def test_original_rebooking_migration_ownership_and_history_protection(tmp_path, monkeypatch, database):
    with owned_engine(tmp_path, monkeypatch, database) as (engine, config):
        command.upgrade(config, "head")
        with engine.connect() as connection:
            assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
        command.downgrade(config, "72c18fba901d")
        assert "employee_rebookings" not in inspect(engine).get_table_names()
        command.upgrade(config, "head")
        now = datetime(2026, 10, 7, 12, tzinfo=timezone.utc)
        with Session(engine) as db:
            init_demo_data(db)
            employee = db.scalar(select(Employee)); institute = employee.institute_id
            service = db.scalar(select(Service))
            for identifier in ("source", "target"):
                db.add(Appointment(id=identifier, institute_id=institute, employee_id=employee.id, service_id=service.id,
                    customer_name="Owned migration fixture", start_time=now, end_time=now+timedelta(hours=1), status="scheduled"))
            db.flush()
            db.add(EmployeeRebooking(id="original", institute_id=institute, employee_id=employee.id, source_appointment_id="source",
                target_appointment_id="target", source_capture={"original": "unchanged"}, booking_capture={"event": "pinned"},
                actor_id="signed", reason="Declared link", idempotency_key="original-key", created_at=now))
            db.flush()
            db.add(RebookingCancellation(id="cancel", institute_id=institute, rebooking_id="original", actor_id="signed",
                reason="Separate correction", idempotency_key="cancel-key", created_at=now))
            db.commit()
            if database == "postgresql":
                for statement, constraint in [
                    ("UPDATE employee_rebookings SET employee_id='foreign-missing' WHERE id='original'", "fk_rebooking_employee_owner"),
                    ("UPDATE employee_rebookings SET target_appointment_id='foreign-missing' WHERE id='original'", "fk_rebooking_target_owner"),
                    ("UPDATE employee_rebookings SET source_appointment_id='foreign-missing' WHERE id='original'", "fk_rebooking_source_booking_owner"),
                    ("UPDATE employee_rebookings SET source_appointment_id=NULL, session_id='foreign-missing' WHERE id='original'", "fk_rebooking_session_owner"),
                    ("UPDATE employee_rebookings SET source_appointment_id=NULL WHERE id='original'", "ck_rebooking_one_source"),
                    ("UPDATE employee_rebookings SET target_appointment_id='source' WHERE id='original'", "ck_rebooking_no_self"),
                    ("UPDATE rebooking_cancellations SET rebooking_id='foreign-missing' WHERE id='cancel'", "fk_rebooking_cancel_owner"),
                ]:
                    with pytest.raises(IntegrityError, match=constraint):
                        with db.begin_nested(): db.execute(text(statement))
        def facts():
            with engine.connect() as connection:
                return [[dict(row) for row in connection.execute(select(model)).mappings()] for model in (EmployeeRebooking, RebookingCancellation)]
        before = facts()
        with pytest.raises(RuntimeError, match="Recorded rebooking history"):
            command.downgrade(config, "72c18fba901d")
        assert facts() == before
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "ea5b7cd43926"
            assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
