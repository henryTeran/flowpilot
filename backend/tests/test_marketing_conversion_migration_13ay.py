from alembic.script import ScriptDirectory
import importlib.util
from pathlib import Path
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
from app.modules.tickets.models import QueueTicket
from app.modules.marketing.models import AudienceOriginal, CampaignOriginal, ContactOriginal, DispatchIntent, DispatchOutcome, ConversionOriginal, ConversionHead
from test_crm_billing_12b import NOW
from test_source_index_migration_10t import owned_engine


def test_conversion_offline_downgrade_requires_history_verification(monkeypatch):
    spec = importlib.util.spec_from_file_location("conversion_migration", Path(__file__).parents[1] / "migrations/versions/4ab1d209558c_marketing_conversion_ledger.py")
    migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
    monkeypatch.setattr(migration.context, "is_offline_mode", lambda: True)
    with pytest.raises(RuntimeError, match="requires online downgrade"): migration.downgrade()


@pytest.mark.parametrize("database", ["sqlite", "postgresql"])
def test_conversion_schema_owned_sources_replay_head_and_preserved_history(tmp_path, monkeypatch, database):
    with owned_engine(tmp_path, monkeypatch, database) as (engine, config):
        if database == "sqlite":
            @event.listens_for(engine, "connect")
            def foreign_keys(connection, record): connection.execute("PRAGMA foreign_keys=ON")
        command.upgrade(config, "head")
        with engine.connect() as connection:
            assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
        command.downgrade(config, "3fa0c198447b")
        assert "marketing_conversion_originals" not in inspect(engine).get_table_names()
        command.upgrade(config, "head")
        with Session(engine) as db:
            init_demo_data(db); owner = db.scalar(select(Institute.id))
            db.add(Institute(id="conversion-foreign", region_id=db.get(Institute, owner).region_id, name="Foreign", city="Test"))
            for index in (1, 2):
                customer = f"conversion-customer-{index}"
                db.add(Customer(id=customer, institute_id=owner, display_name=customer, phone=None, search_name=customer,
                    phone_digits="", idempotency_key=customer, creation_fingerprint="f" * 64, created_at=NOW, created_by="manager"))
            db.add(AudienceOriginal(id="conversion-audience", institute_id=owner, actor_id="manager", reason="Schema fixture",
                idempotency_key="conversion-audience", captured_at=NOW, request={}, summary={}))
            db.flush()
            db.add(CampaignOriginal(id="conversion-send", institute_id=owner, campaign_id="conversion-campaign", previous_id=None,
                audience_id="conversion-audience", template_original_id=None, actor_id="manager", reason="Schema fixture",
                idempotency_key="conversion-send", created_at=NOW, request={}, revision={}))
            for index in (1, 2):
                customer = f"conversion-customer-{index}"
                db.add(ContactOriginal(id=f"conversion-contact-{index}", institute_id=owner, customer_id=customer, previous_id=None,
                    actor_id="manager", reason="Schema fixture", idempotency_key=f"conversion-contact-{index}", created_at=NOW, declaration={}))
                db.add(QueueTicket(id=f"conversion-ticket-{index}", institute_id=owner, ticket_number=f"conversion-{index}",
                    customer_id=customer, status="paid", arrival_time=NOW, paid_at=NOW, currency="CHF"))
            db.flush()
            for index in (1, 2):
                db.add(DispatchIntent(id=f"conversion-intent-{index}", institute_id=owner, campaign_id="conversion-campaign",
                    approval_id="conversion-send", customer_id=f"conversion-customer-{index}", contact_id=f"conversion-contact-{index}",
                    actor_id="manager", reason="Schema fixture", idempotency_key=f"conversion-intent-{index}", created_at=NOW,
                    request_fingerprint="f" * 64, submission={}))
            db.flush()
            for index in (1, 2):
                db.add(DispatchOutcome(id=f"conversion-outcome-{index}", institute_id=owner, intent_id=f"conversion-intent-{index}", previous_id=None,
                    actor_id="worker", reason="Schema fixture", idempotency_key=f"conversion-outcome-{index}", created_at=NOW, result={}))
            db.commit()
            def original(identity, ticket="conversion-ticket-1", **patch):
                values = dict(id=identity, institute_id=owner, ticket_id=ticket, campaign_id="conversion-campaign", intent_id="conversion-intent-1",
                    authorization_id="conversion-send", accepted_outcome_id="conversion-outcome-1", previous_id=None, action="linked",
                    actor_id="manager", reason="Schema attribution", idempotency_key=identity, created_at=NOW, request={"key": identity},
                    attribution={"retained": identity}, attribution_fingerprint="a" * 64)
                return ConversionOriginal(**(values | patch))
            db.add_all([original("linked"), original("other-ticket", "conversion-ticket-2")]); db.flush()
            db.add(ConversionHead(institute_id=owner, ticket_id="conversion-ticket-1", original_id="linked")); db.commit()
            db.add(original("retracted", previous_id="linked", action="retracted")); db.flush()
            db.get(ConversionHead, (owner, "conversion-ticket-1")).original_id = "retracted"; db.commit()
            for row in [original("foreign", institute_id="conversion-foreign"), original("missing-ticket", ticket="absent"),
                original("wrong-root", campaign_id="other"), original("missing-intent", intent_id="absent"),
                original("wrong-outcome", accepted_outcome_id="conversion-outcome-2"), original("missing-send", authorization_id="absent"),
                original("duplicate-key", idempotency_key="linked"), original("cross-ticket", previous_id="other-ticket"),
                original("self", previous_id="self"), original("invalid-action", action="deleted"), original("empty-retraction", action="retracted"),
                ConversionHead(institute_id=owner, ticket_id="conversion-ticket-2", original_id="retracted"),
                ConversionHead(institute_id=owner, ticket_id="conversion-ticket-1", original_id="linked")]:
                db.add(row)
                with pytest.raises(DBAPIError): db.commit()
                db.rollback()
            assert db.get(ConversionOriginal, "linked").attribution == {"retained": "linked"}
            assert db.get(ConversionHead, (owner, "conversion-ticket-1")).original_id == "retracted"
        with pytest.raises(RuntimeError, match="conversion history cannot be removed"):
            command.downgrade(config, "3fa0c198447b")
        with engine.begin() as connection: connection.execute(text("DELETE FROM marketing_conversion_heads"))
        with pytest.raises(RuntimeError, match="conversion history cannot be removed"):
            command.downgrade(config, "3fa0c198447b")
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == ScriptDirectory.from_config(config).get_current_head()
            assert connection.scalar(text("SELECT COUNT(*) FROM marketing_conversion_originals")) == 3
