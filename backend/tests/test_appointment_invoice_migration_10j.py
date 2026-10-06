import os
from datetime import timedelta
from pathlib import Path
from uuid import uuid4
import pytest
from alembic import command
from alembic.config import Config
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from app.core.config import settings
from app.database.base import Base
from app.modules.dev.routes import init_demo_data
from app.modules.institutes.models import Institute
from app.modules.services.models import Service
from app.modules.tickets.models import QueueTicket, TicketLine
from app.shared.time import utcnow


from app.modules.appointments.models import Appointment, AppointmentInvoiceLine
from app.modules.employees.models import Employee
@pytest.mark.parametrize("database", ["sqlite", "postgresql"])
def test_appointment_invoice_migration_no_backfill_and_guard(tmp_path, monkeypatch, database):
    admin = None
    if database == "postgresql":
        source = os.environ.get("FLOWPILOT_TEST_POSTGRES_URL")
        if not source:
            pytest.skip("FLOWPILOT_TEST_POSTGRES_URL required")
        admin = create_engine(source)
        assert admin.dialect.name == "postgresql"
        schema = "fp_migration_" + uuid4().hex
        with admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        url = make_url(source).update_query_dict({"options": f"-csearch_path={schema}"}).render_as_string(hide_password=False)
    else:
        url = f"sqlite:///{tmp_path / 'invoice.sqlite'}"
    monkeypatch.setattr(settings, "DATABASE_URL", url)
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
    engine = create_engine(url)
    try:
        command.upgrade(config, "head")
        command.downgrade(config, "e84539c0a2b7")
        with Session(engine) as db:
            init_demo_data(db)
            institute = db.scalar(select(Institute.id))
            service = db.scalar(select(Service.id))
            employee = db.scalar(select(Employee.id).where(Employee.institute_id == institute))
            now = utcnow()
            db.add(QueueTicket(id="legacy-invoice", institute_id=institute, ticket_number="LEGACY", status="ready_for_checkout", arrival_time=now, total_amount=10))
            db.flush()
            db.add(TicketLine(id="legacy-line", ticket_id="legacy-invoice", service_id=service, quantity=1, unit_price=10, total=10, duration_minutes=10, revenue_category="care"))
            db.add(Appointment(id="legacy-booking", institute_id=institute, employee_id=employee, service_id=service, customer_name="Legacy", start_time=now, end_time=now+timedelta(minutes=10), status="completed", checkout_ticket_id="legacy-invoice"))
            db.commit()
        command.upgrade(config, "head")
        with Session(engine) as db:
            assert db.get(AppointmentInvoiceLine, "legacy-booking") is None
            assert db.get(Appointment, "legacy-booking").checkout_ticket_id == "legacy-invoice"
            # A populated original fact makes downgrade refuse BEFORE any DDL.
            db.add(AppointmentInvoiceLine(appointment_id="legacy-booking", institute_id=institute, ticket_id="legacy-invoice", ticket_line_id="legacy-line", actor_id="signed", occurred_at=now))
            db.commit()
        with pytest.raises(RuntimeError, match="cannot preserve original invoice history"):
            command.downgrade(config, "e84539c0a2b7")
        with Session(engine) as db:
            assert db.get(AppointmentInvoiceLine, "legacy-booking").ticket_line_id == "legacy-line"
        with engine.connect() as connection:
            assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
    finally:
        engine.dispose()
        if admin:
            with admin.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            admin.dispose()
