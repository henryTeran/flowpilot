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
from app.modules.inventory import reorders, orders
from app.modules.inventory.order_schemas import OrderCreate
from test_purchase_orders_10l import setup


@pytest.mark.parametrize("database",["sqlite","postgresql"])
def test_reorder_migration_preserves_orders_and_protects_retained_proposals(tmp_path,monkeypatch,database):
    admin = None
    if database == "postgresql":
        source = os.environ.get("FLOWPILOT_TEST_POSTGRES_URL")
        if not source:pytest.skip("FLOWPILOT_TEST_POSTGRES_URL required")
        admin = create_engine(source)
        schema = "fp_test_migration_"+uuid4().hex
        with admin.begin() as conn:conn.execute(text(f'CREATE SCHEMA "{schema}"'))
        url = make_url(source).update_query_dict({"options":f"-csearch_path={schema}"}).render_as_string(hide_password=False)
    else:url = f"sqlite:///{tmp_path / 'reorder.sqlite'}"
    monkeypatch.setattr(settings,"DATABASE_URL",url)
    config = Config()
    config.set_main_option("script_location",str(Path(__file__).resolve().parents[1]/"migrations"))
    engine = create_engine(url)
    try:
        command.upgrade(config,"head")
        command.downgrade(config,"0673d4b5f0a7")  # empty proposal table may be removed
        with Session(engine) as db:
            init_demo_data(db)
            institute = db.scalar(select(Institute.id))
            serum,_,terms = setup(db,institute)
            old = orders.create(db,institute,OrderCreate(**terms),"manager").model_dump(mode="json")
        command.upgrade(config,"head")
        with engine.connect() as conn:
            assert compare_metadata(MigrationContext.configure(conn),Base.metadata) == []
        with Session(engine) as db:
            assert orders.snapshot(db,orders.require_order(db,institute,old["id"])).model_dump(mode="json") == old
            selection = reorders.Selection(supplier_id=terms["supplier_id"],item_ids=(serum,),pending_order_assumption="ignore_pending_orders")
            preview = reorders.preview(db,institute,selection)
            request = reorders.Request(selection=selection,expected_state_fingerprint=preview.state_fingerprint,reason="Reviewed exact reorder",idempotency_key="migrated-proposal")
            original = reorders.create(db,institute,request,"manager")
        with pytest.raises(RuntimeError,match="cannot be removed"):
            command.downgrade(config,"0673d4b5f0a7")
        with Session(engine) as db:
            assert reorders.require(db,institute,original.original["id"]) == original
            assert orders.snapshot(db,orders.require_order(db,institute,old["id"])).model_dump(mode="json") == old
    finally:
        engine.dispose()
        if admin is not None:
            with admin.begin() as conn:conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            admin.dispose()
