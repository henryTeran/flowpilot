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
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.config import settings
from app.database.base import Base
from app.modules.dev.routes import init_demo_data
from app.modules.institutes.models import Institute
from app.modules.services.models import Service
from app.modules.tickets.models import QueueTicket, TicketLine
from app.modules.tickets.service import remove_checkout_ticket_line
from app.shared.time import utcnow


@pytest.mark.parametrize("database", ["sqlite", "postgresql"])
def test_retained_invoice_migration_original_terms_and_signed_downgrade_guard(tmp_path, monkeypatch, database):
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
        command.downgrade(config, "d73428bf91a6")
        with Session(engine) as db:
            init_demo_data(db)
            institute = db.scalar(select(Institute.id))
            service = db.scalar(select(Service.id))
            db.add(QueueTicket(id="invoice", institute_id=institute, ticket_number="OLD-1", status="ready_for_checkout", arrival_time=utcnow(), total_amount=49.36))
            db.flush()
            for line_id in ("original-1", "original-2"):
                db.execute(text("INSERT INTO ticket_lines (id,ticket_id,service_id,quantity,unit_price,total,duration_minutes,revenue_category) VALUES (:id,'invoice',:service,2,12.34,24.68,10,'care')"), dict(id=line_id, service=service))
            db.commit()
        command.upgrade(config, "head")
        with Session(engine) as db:
            original = db.get(TicketLine, "original-1")
            assert original.invoice_removed_at is None and original.invoice_removed_by_actor is None
            assert str(original.total) == "24.68" and original.quantity == 2
            with pytest.raises(IntegrityError):
                db.execute(text("UPDATE ticket_lines SET invoice_removed_at=:time WHERE id='original-1'"), dict(time=utcnow()))
            db.rollback()
            remove_checkout_ticket_line(db, "invoice", "original-1", "signed-cashier")
            assert db.get(QueueTicket, "invoice").total_amount == original.total
            at = original.invoice_removed_at
        with pytest.raises(RuntimeError, match="cannot preserve signed correction history"):
            command.downgrade(config, "d73428bf91a6")
        with Session(engine) as db:
            original = db.get(TicketLine, "original-1")
            assert original.invoice_removed_at == at and original.invoice_removed_by_actor == "signed-cashier"
            assert original.quantity == 2 and str(original.total) == "24.68"
        with engine.connect() as connection:
            assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
    finally:
        engine.dispose()
        if admin:
            with admin.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            admin.dispose()
