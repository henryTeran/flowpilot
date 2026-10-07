import os
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from uuid import uuid4
import pytest
from alembic import command
from alembic.config import Config
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, select, text, inspect, insert
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from app.core.config import settings
from app.database.base import Base
from app.modules.dev.routes import init_demo_data
from app.modules.institutes.models import Institute
from app.modules.employees.models import Employee
from app.modules.services.models import Service
from app.modules.appointments.models import Appointment
from app.modules.planning.models import ServiceSession
from app.modules.tickets.models import QueueTicket
from app.modules.inventory.models import StockItem, StockMovement, StockPurchaseOrder, StockPurchaseReceipt
from app.modules.inventory import orders, observed
from app.modules.inventory.order_schemas import OrderCreate, ReceiptCreate
from app.modules.inventory.projection import ProjectionWindow
from app.shared.time import utcnow
from test_purchase_orders_10l import setup, reception
from test_postgres_scheduling_4d import postgres_flow


@contextmanager
def owned_engine(tmp_path, monkeypatch, database):
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
        url = f"sqlite:///{tmp_path / 'source-index.sqlite'}"
    monkeypatch.setattr(settings, "DATABASE_URL", url)
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
    engine = create_engine(url)
    try:
        yield engine, config
    finally:
        engine.dispose()
        if admin:
            with admin.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            admin.dispose()


def facts(engine):
    with engine.connect() as connection:
        return {model.__tablename__: [dict(row) for row in connection.execute(select(model.__table__).order_by(
            model.__table__.c.id)).mappings()] for model in (StockItem, StockMovement, StockPurchaseOrder,
                StockPurchaseReceipt, Appointment, ServiceSession, QueueTicket)}


@pytest.mark.parametrize("database", ["sqlite", "postgresql"])
def test_source_indexes_roundtrip_preserves_populated_history_and_blocked_downgrade_schema(tmp_path, monkeypatch, database):
    with owned_engine(tmp_path, monkeypatch, database) as (engine, config):
        command.upgrade(config, "1b786cf3d5ea")
        with Session(engine) as db:
            init_demo_data(db)
            institute = db.scalar(select(Institute.id))
            serum, _, terms = setup(db, institute)
            order = orders.create(db, institute, OrderCreate(**terms), "signed")
            orders.receive(db, institute, order.id, ReceiptCreate(**reception(serum)), "signed")
            db.add(Appointment(id="index-history", institute_id=institute,
                service_id=db.scalar(select(Service.id)), employee_id=db.scalar(select(Employee.id).where(Employee.institute_id == institute)),
                customer_name="Owned historical source", start_time=utcnow()-timedelta(days=1, minutes=15),
                end_time=utcnow()-timedelta(days=1), actual_end_time=utcnow()-timedelta(days=1), status="completed"))
            db.commit()
        before = facts(engine)
        command.upgrade(config, "head")
        assert facts(engine) == before
        for table, names in (("appointments", {"ix_appointment_inst_status_actual_end", "ix_appointment_inst_status_slot"}),
                             ("service_sessions", {"ix_session_inst_status_real_end"}),
                             ("queue_tickets", {"ix_queue_ticket_inst_status"})):
            assert names <= {index["name"] for index in inspect(engine).get_indexes(table)}
        command.downgrade(config, "1b786cf3d5ea")  # Removing only indexes is safe with facts present.
        assert facts(engine) == before
        assert "ix_queue_ticket_inst_status" not in {index["name"] for index in inspect(engine).get_indexes("queue_tickets")}
        command.upgrade(config, "head")
        with pytest.raises(RuntimeError, match="cannot preserve signed purchase history"):
            command.downgrade(config, "0a675be2c4d9")
        assert facts(engine) == before
        with engine.connect() as connection:
            assert connection.scalar(text("select version_num from alembic_version")) == "ea5b7cd43926"
            assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []


def test_postgres_actual_observed_source_plan_uses_scoped_completion_index(postgres_flow):
    engine, institute, employee, service = postgres_flow
    now = utcnow()
    with Session(engine) as db:
        db.execute(insert(Appointment), [dict(id=f"source-plan-{i}", institute_id=institute,
            employee_id=employee, service_id=service, customer_name="Owned source plan fixture",
            start_time=now-timedelta(minutes=10*i+15), end_time=now-timedelta(minutes=10*i),
            actual_end_time=None if i % 500 == 0 else now-timedelta(minutes=10*i), status="completed") for i in range(6000)])
        db.commit()
        db.execute(text("ANALYZE appointments"))
        window = ProjectionWindow.create(now, now+timedelta(days=1), now-timedelta(days=1), now, now)
        source = observed.sources(institute, window)
        query = select(source).order_by(source.c.source_kind, source.c.source_id, source.c.basis_id)
        sql = str(query.compile(engine, compile_kwargs={"literal_binds": True}))
        plan = db.scalar(text("EXPLAIN (FORMAT JSON) " + sql))
        def indexes(node):
            yield node.get("Index Name")
            for child in node.get("Plans", []):
                yield from indexes(child)
        assert "ix_appointment_inst_status_actual_end" in set(indexes(plan[0]["Plan"]))
