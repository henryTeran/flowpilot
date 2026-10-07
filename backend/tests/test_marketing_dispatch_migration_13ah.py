from alembic.script import ScriptDirectory
import pytest
import importlib.util
from pathlib import Path
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
from app.modules.marketing.models import AudienceOriginal, CampaignOriginal, ContactOriginal, DispatchIntent, DispatchOutcome, DispatchHead
from test_crm_billing_12b import NOW
from test_source_index_migration_10t import owned_engine

def test_dispatch_offline_downgrade_requires_history_verification(monkeypatch):
    spec = importlib.util.spec_from_file_location("dispatch_migration", Path(__file__).parents[1] / "migrations/versions/3fa0c198447b_marketing_dispatch_ledger.py")
    migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
    monkeypatch.setattr(migration.context, "is_offline_mode", lambda: True)
    with pytest.raises(RuntimeError, match="requires online downgrade"): migration.downgrade()

@pytest.mark.parametrize("database", ["sqlite", "postgresql"])
def test_dispatch_schema_pins_owned_sources_replay_recipient_and_outcome_history(tmp_path, monkeypatch, database):
    with owned_engine(tmp_path, monkeypatch, database) as (engine, config):
        if database == "sqlite":
            @event.listens_for(engine, "connect")
            def foreign_keys(connection, record): connection.execute("PRAGMA foreign_keys=ON")
        command.upgrade(config, "head")
        with engine.connect() as connection:
            assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
        command.downgrade(config, "2e9fb087336a")
        assert "marketing_dispatch_intents" not in inspect(engine).get_table_names()
        command.upgrade(config, "head")
        with Session(engine) as db:
            init_demo_data(db); owner = db.scalar(select(Institute.id))
            db.add(Institute(id="dispatch-foreign", region_id=db.get(Institute, owner).region_id, name="Foreign", city="Test")); db.flush()
            for c in ("one", "two"):
                db.add(Customer(id=c, institute_id=owner, display_name=c, phone=None, search_name=c, phone_digits="", idempotency_key=c,
                    creation_fingerprint="f" * 64, created_at=NOW, created_by="manager"))
            db.add(AudienceOriginal(id="aud", institute_id=owner, actor_id="manager", reason="Schema source", idempotency_key="aud", captured_at=NOW, request={}, summary={}))
            db.flush()
            db.add(CampaignOriginal(id="approved", institute_id=owner, campaign_id="campaign", previous_id=None, audience_id="aud", template_original_id=None,
                actor_id="manager", reason="Schema source", idempotency_key="approved", created_at=NOW, request={}, revision={}))
            db.add(CampaignOriginal(id="approved-two", institute_id=owner, campaign_id="campaign", previous_id=None, audience_id="aud", template_original_id=None,
                actor_id="manager", reason="Schema source", idempotency_key="approved-two", created_at=NOW, request={}, revision={}))
            for c in ("one", "two"):
                db.add(ContactOriginal(id="contact-" + c, institute_id=owner, customer_id=c, previous_id=None, actor_id="manager", reason="Schema source",
                    idempotency_key="contact-" + c, created_at=NOW, declaration={}))
            db.flush()
            def intent(identity, customer="one", **patch):
                values = dict(id=identity, institute_id=owner, campaign_id="campaign", approval_id="approved", customer_id=customer, contact_id="contact-" + customer,
                    actor_id="manager", reason="Schema intent", idempotency_key=identity, created_at=NOW, request_fingerprint="a" * 64, submission={"retained": identity})
                return DispatchIntent(**{**values, **patch})
            def outcome(identity, target="intent-one", previous=None, **patch):
                return DispatchOutcome(**{**dict(id=identity, institute_id=owner, intent_id=target, previous_id=previous, actor_id="worker", reason="Schema result",
                    idempotency_key=identity, created_at=NOW, result={"retained": identity}), **patch})
            db.add_all([intent("intent-one"), intent("intent-two", "two")]); db.flush()
            db.add_all([outcome("unknown"), outcome("other", "intent-two")]); db.flush()
            db.add(DispatchHead(institute_id=owner, intent_id="intent-one", original_id="unknown")); db.commit()
            db.add(outcome("accepted", previous="unknown")); db.flush()
            db.get(DispatchHead, (owner, "intent-one")).original_id = "accepted"; db.commit()
            invalid = [intent("duplicate-recipient"), intent("wrong-contact", approval_id="approved-two", contact_id="contact-two"), intent("foreign", institute_id="dispatch-foreign"),
                intent("wrong-root", approval_id="approved-two", campaign_id="other"), intent("duplicate-key", "two", approval_id="approved-two", idempotency_key="intent-one"),
                outcome("cross-intent", previous="other"), outcome("self", previous="self"), outcome("foreign-outcome", institute_id="dispatch-foreign"),
                outcome("duplicate-outcome-key", idempotency_key="unknown"), outcome("missing-intent", target="missing"),
                DispatchHead(institute_id=owner, intent_id="intent-two", original_id="accepted")]
            for row in invalid:
                db.add(row)
                with pytest.raises(DBAPIError): db.commit()
                db.rollback()
            assert db.get(DispatchOutcome, "unknown").result == {"retained": "unknown"}
            assert db.get(DispatchIntent, "intent-one").submission == {"retained": "intent-one"}
            assert db.get(DispatchHead, (owner, "intent-one")).original_id == "accepted"
        for remove_results in (False, True):
            if remove_results:
                with engine.begin() as connection:
                    connection.execute(text("DELETE FROM marketing_dispatch_heads"))
                    connection.execute(text("DELETE FROM marketing_dispatch_outcomes WHERE previous_id IS NOT NULL"))
                    connection.execute(text("DELETE FROM marketing_dispatch_outcomes"))
            with pytest.raises(RuntimeError, match="dispatch history cannot be removed"):
                command.downgrade(config, "2e9fb087336a")
            with engine.connect() as connection:
                assert connection.scalar(text("SELECT version_num FROM alembic_version")) == ScriptDirectory.from_config(config).get_current_head()
                assert connection.scalar(text("SELECT COUNT(*) FROM marketing_dispatch_intents")) == 2
