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
from app.modules.inventory import service, recipes
from app.modules.inventory.models import StockItem, StockMovement, StockRecipe, StockRecipeLine
from app.modules.inventory.schemas import ItemCreate, MovementCreate, RecipeCreate
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
        command.upgrade(config, "head")
        with Session(engine) as db:
            init_demo_data(db)
            institute = db.scalar(select(Institute.id))
            row = service.create_item(db, institute, ItemCreate(**item()), "manager")
            service.move(db, institute, row.id, MovementCreate(**movement()), "manager")
            recipes.create(db, institute, db.scalar(select(Service.id)), RecipeCreate(
                base_revision=0, enabled=True, entries=[dict(item_id=row.id, quantity="1.125")],
                reason="Migration recipe", idempotency_key="migration-recipe"), "manager")
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
            assert len(list(db.scalars(select(StockMovement)))) == 1
            assert len(list(db.scalars(select(StockRecipe)))) == 1
            assert len(list(db.scalars(select(StockRecipeLine)))) == 1
            assert service.balance_milli(db, institute, row.id) == 10125
        with engine.connect() as connection:
            assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
    finally:
        engine.dispose()
        if admin:
            with admin.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            admin.dispose()
