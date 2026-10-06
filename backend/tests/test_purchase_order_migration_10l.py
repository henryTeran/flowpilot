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


from test_purchase_orders_10l import setup, reception
from app.modules.inventory import orders, service as stock
from app.modules.inventory.order_schemas import OrderCreate, ReceiptCreate
from app.modules.inventory.schemas import MovementCreate
from test_inventory_10a import movement
from app.modules.inventory.models import StockPurchaseOrder, StockPurchaseReceipt, StockMovement


@pytest.mark.parametrize("database", ["sqlite", "postgresql"])
def test_purchase_migration_preserves_ledger_and_signed_history(tmp_path, monkeypatch, database):
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
        command.downgrade(config, "0a675be2c4d9")
        command.upgrade(config, "head")
        command.downgrade(config, "0a675be2c4d9")
        with Session(engine) as db:
            init_demo_data(db)
            institute = db.scalar(select(Institute.id))
            serum, cartridge, payload = setup(db, institute)
            original_move = stock.move(db, institute, serum, MovementCreate(**movement(quantity="1.125")), "signed").model_dump(mode="json")
        command.upgrade(config, "head")
        with Session(engine) as db:
            assert db.scalars(select(StockPurchaseOrder)).all() == []
            assert stock.balance_milli(db, institute, serum) == 1125
            assert stock.read_movement(db.get(StockMovement, original_move["id"]), "ml").model_dump(mode="json") == original_move
            original_order = orders.create(db, institute, OrderCreate(**payload), "signed").model_dump(mode="json")
            original_receipt = orders.receive(db, institute, original_order["id"], ReceiptCreate(**reception(serum)), "signed").model_dump(mode="json")
            assert stock.balance_milli(db, institute, serum) == 3250
            assert stock.read_movement(db.get(StockMovement, original_move["id"]), "ml").model_dump(mode="json") == original_move
        with pytest.raises(RuntimeError, match="cannot preserve signed purchase history"):
            command.downgrade(config, "0a675be2c4d9")
        with Session(engine) as db:
            assert orders.snapshot(db, db.get(StockPurchaseOrder, original_order["id"])).model_dump(mode="json") == original_order
            assert orders.receipt_snapshot(db, db.get(StockPurchaseReceipt, original_receipt["id"])).model_dump(mode="json") == original_receipt
            assert stock.balance_milli(db, institute, serum) == 3250
        with engine.connect() as connection:
            assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
    finally:
        engine.dispose()
        if admin:
            with admin.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            admin.dispose()
