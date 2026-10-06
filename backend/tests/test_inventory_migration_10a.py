import os
from pathlib import Path
from uuid import uuid4
import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.config import settings
from app.database.base import Base
from app.modules.dev.routes import init_demo_data
from app.modules.institutes.models import Institute
from app.modules.inventory import service, recipes, consumptions
from app.modules.inventory.models import StockItem, StockMovement, StockRecipe, StockRecipeLine, StockServiceBasis, StockConsumption
from app.modules.inventory.schemas import ItemCreate, MovementCreate, RecipeCreate, ConsumptionCreate
from app.modules.services.models import Service
from app.shared.time import utcnow
from test_inventory_10a import item, movement


@pytest.mark.parametrize("database", ["sqlite", "postgresql"])
def test_inventory_migration_empty_roundtrip_and_populated_refusal(tmp_path, monkeypatch, database):
    admin = None
    if database == "postgresql":
        postgres_url = os.environ.get("FLOWPILOT_TEST_POSTGRES_URL")
        if not postgres_url:
            pytest.skip("Explicit validation PostgreSQL URL required")
        admin = create_engine(postgres_url)
        assert admin.dialect.name == "postgresql"
        schema = "fp_migration_" + uuid4().hex
        with admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        url = make_url(postgres_url).update_query_dict({"options": f"-csearch_path={schema}"}).render_as_string(hide_password=False)
    else:
        url = f"sqlite:///{tmp_path / 'inventory.sqlite'}"
    monkeypatch.setattr(settings, "DATABASE_URL", url)
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
    engine = create_engine(url)
    try:
        command.upgrade(config, "head")
        with engine.connect() as connection:
            assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
        command.downgrade(config, "93f0348baef2")
        command.upgrade(config, "c62317ae80f5")
        with Session(engine) as db:
            init_demo_data(db)
            institute = db.scalar(select(Institute.id))
            row = service.create_item(db, institute, ItemCreate(**item()), "manager")
            # Original ledger facts exist before the nullable linkage migration.
            db.execute(text("INSERT INTO stock_movements (id,institute_id,item_id,kind,quantity_milli,reason,actor_id,idempotency_key,occurred_at) VALUES (:id,:institute,:item,'receipt',10125,:reason,'manager',:key,:time)"),
                dict(id="legacy-delivery", institute=institute, item=row.id, reason=movement()["reason"], key=movement()["idempotency_key"], time=utcnow().isoformat()))
            db.commit()
            recipes.create(db, institute, db.scalar(select(Service.id)), RecipeCreate(
                base_revision=0, enabled=True, entries=[dict(item_id=row.id, quantity="1.125")],
                reason="Migration recipe", idempotency_key="migration-recipe"), "manager")
            from app.modules.tickets.schemas import TicketCreate
            from app.modules.tickets.service import create_queue_ticket
            from app.modules.planning.service import start_service_session
            from app.modules.employees.models import Employee
            service_id = db.scalar(select(Service.id))
            employee = db.scalar(select(Employee).where(Employee.institute_id == institute))
            employee.status = "available"
            db.commit()
            ticket = create_queue_ticket(db, TicketCreate(institute_id=institute, service_id=service_id))
            start_service_session(db, ticket.id, employee.id, actor_id="migration-operator")
        command.upgrade(config, "head")
        with Session(engine) as db:
            legacy = db.get(StockMovement, "legacy-delivery")
            assert legacy.consumption_id is None and legacy.quantity_milli == 10125
            assert legacy.actor_id == "manager" and legacy.reason == movement()["reason"]
            assert legacy.idempotency_key == movement()["idempotency_key"]
            basis = db.scalar(select(StockServiceBasis))
            from app.modules.planning.service import finish_service_session
            finish_service_session(db, basis.session_id)
            confirmed = consumptions.create(db, institute, basis.id, ConsumptionCreate(
                entries=[dict(item_id=row.id, quantity="1.125")], reason="Migration actual consumption",
                idempotency_key="migration-consumption"), "manager")
            assert confirmed.matches_norm is True
            if database == "postgresql":
                original = db.get(Institute, institute)
                db.add(Institute(id="other", region_id=original.region_id, name="Other", city="Other", timezone=original.timezone, status="active"))
                db.commit()
                db.add(StockMovement(id="foreign-movement", institute_id="other", item_id=row.id,
                    kind="receipt", quantity_milli=1000, reason="Invalid foreign owner", actor_id="manager",
                    idempotency_key="foreign", occurred_at=utcnow()))
                with pytest.raises(IntegrityError):
                    db.commit()
                db.rollback()
        with pytest.raises(RuntimeError, match="cannot preserve signed inventory history"):
            command.downgrade(config, "93f0348baef2")
        with Session(engine) as db:
            assert len(list(db.scalars(select(StockItem)))) == 1
            assert len(list(db.scalars(select(StockMovement)))) == 2
            assert len(list(db.scalars(select(StockRecipe)))) == 1
            assert len(list(db.scalars(select(StockRecipeLine)))) == 1
            assert len(list(db.scalars(select(StockServiceBasis)))) == 1
            assert len(list(db.scalars(select(StockConsumption)))) == 1
            assert service.balance_milli(db, institute, row.id) == 9000
        with engine.connect() as connection:
            assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
    finally:
        engine.dispose()
        if admin:
            with admin.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            admin.dispose()
