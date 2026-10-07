import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import event, inspect, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.database.base import Base
from app.modules.customers.models import Customer
from app.modules.dev.routes import init_demo_data
from app.modules.institutes.models import Institute
from app.modules.marketing.models import ContactOriginal, ContactHead
from test_crm_billing_12b import NOW
from test_source_index_migration_10t import owned_engine


@pytest.mark.parametrize("database", ["sqlite", "postgresql"])
def test_contact_schema_ownership_replay_and_retained_history(tmp_path, monkeypatch, database):
    with owned_engine(tmp_path, monkeypatch, database) as (engine, config):
        if database == "sqlite":
            @event.listens_for(engine, "connect")
            def foreign_keys(connection, record): connection.execute("PRAGMA foreign_keys=ON")
        command.upgrade(config, "head")
        with engine.connect() as connection:
            assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
        command.downgrade(config, "1d8eaf762259")
        assert "marketing_contact_originals" not in inspect(engine).get_table_names()
        command.upgrade(config, "head")
        with Session(engine) as db:
            init_demo_data(db)
            institute = db.scalar(select(Institute.id))
            foreign = "contact-schema-foreign"
            db.add(Institute(id=foreign, region_id=db.get(Institute, institute).region_id, name="Foreign", city="Test")); db.flush()
            for identifier, owner in [("one", institute), ("two", institute), ("foreign", foreign)]:
                db.add(Customer(id=identifier, institute_id=owner, display_name=identifier, phone=None, search_name=identifier,
                    phone_digits="", idempotency_key=identifier, creation_fingerprint="f" * 64, created_at=NOW, created_by="manager"))
            db.flush()
            def original(identifier, customer="one", owner=institute, previous=None, key=None):
                return ContactOriginal(id=identifier, institute_id=owner, customer_id=customer, previous_id=previous,
                    actor_id="manager", reason="Explicit schema fixture", idempotency_key=key or identifier, created_at=NOW,
                    declaration={"schema_fixture": True})
            db.add_all([original("o"), original("other", customer="two"), original("foreign-o", customer="foreign", owner=foreign)]); db.flush()
            db.add(ContactHead(institute_id=institute, customer_id="one", original_id="o")); db.commit()
            before = db.get(ContactOriginal, "o").declaration.copy()
            db.add(original("correction", previous="o")); db.flush()
            db.get(ContactHead, (institute, "one")).original_id = "correction"; db.commit()
            for row in [original("cross-customer", previous="other"), original("cross-institute", previous="foreign-o"),
                        original("duplicate-key", key="o"), original("self", previous="self"), original("missing-customer", customer="missing"),
                        ContactHead(institute_id=institute, customer_id="two", original_id="o"),
                        ContactHead(institute_id=foreign, customer_id="one", original_id="o")]:
                db.add(row)
                with pytest.raises(DBAPIError): db.commit()
                db.rollback()
            assert db.get(ContactOriginal, "o").declaration == before
            assert db.get(ContactHead, (institute, "one")).original_id == "correction"
        with pytest.raises(RuntimeError, match="contact history cannot be removed"):
            command.downgrade(config, "1d8eaf762259")
        assert "marketing_contact_heads" in inspect(engine).get_table_names()
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "2e9fb087336a"
            assert connection.scalar(text("SELECT COUNT(*) FROM marketing_contact_originals")) == 4
        # An original alone (without a current pointer) still protects retained history.
        with engine.begin() as connection: connection.execute(text("DELETE FROM marketing_contact_heads"))
        with pytest.raises(RuntimeError, match="contact history cannot be removed"):
            command.downgrade(config, "1d8eaf762259")
