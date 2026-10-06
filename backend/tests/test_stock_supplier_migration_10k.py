import os
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


from app.modules.inventory.models import StockSupplier
from app.modules.inventory.schemas import SupplierCreate
from app.modules.inventory import suppliers
from test_stock_suppliers_10k import terms


@pytest.mark.parametrize("database", ["sqlite", "postgresql"])
def test_supplier_migration_empty_roundtrip_no_backfill_and_guard(tmp_path, monkeypatch, database):
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
        command.downgrade(config, "f9564ad1b3c8")
        command.upgrade(config, "head")
        command.downgrade(config, "f9564ad1b3c8")
        with Session(engine) as db:
            init_demo_data(db)
            institute = db.scalar(select(Institute.id))
            service = db.scalar(select(Service.id))
            db.add(QueueTicket(id="original-invoice", institute_id=institute, ticket_number="ORIGINAL", status="ready_for_checkout", arrival_time=utcnow(), total_amount=10))
            db.flush()
            db.add(TicketLine(id="original-line", ticket_id="original-invoice", service_id=service, quantity=1, unit_price=10, total=10, duration_minutes=10, revenue_category="care"))
            db.commit()
        command.upgrade(config, "head")
        with Session(engine) as db:
            assert db.scalars(select(StockSupplier)).all() == []
            assert str(db.get(TicketLine, "original-line").total) == "10.00"
            original = suppliers.create(db, institute, SupplierCreate(**terms()), "signed").model_dump(mode="json")
        with pytest.raises(RuntimeError, match="cannot preserve signed supplier history"):
            command.downgrade(config, "f9564ad1b3c8")
        with Session(engine) as db:
            assert suppliers.snapshot(db.get(StockSupplier, original["id"])).model_dump(mode="json") == original
            assert db.get(TicketLine, "original-line").quantity == 1
        with engine.connect() as connection:
            assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
    finally:
        engine.dispose()
        if admin:
            with admin.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            admin.dispose()
