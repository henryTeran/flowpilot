from datetime import timedelta
import json
from pathlib import Path
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from fastapi import HTTPException
import pytest
from sqlalchemy import text, select, func
from sqlalchemy.orm import Session
from app.database import session
from app.modules.marketing import invoke, dispatch_intents, dispatch_worker, dispatch_outcomes, contact_originals
from app.modules.marketing.models import DispatchOutcome
from test_marketing_recipient_observations_13z import setup
from test_marketing_dispatch_intents_13ai import configure, body
from test_marketing_dispatch_worker_13ak import Fake, declare_send
from test_marketing_contact_originals_13y import body as contact_body
from test_marketing_transports_13al import request
from test_crm_billing_12b import NOW
from test_postgres_scheduling_4d import postgres_flow
import app.main as main_module
from test_ticket_workflow import _bootstrap_reference_data


def fixture(engine, institute, monkeypatch):
    _, approval, contact = setup(engine, institute, monkeypatch)
    configure(institute, monkeypatch)
    account = request("email").account.model_copy(update={"institute_id": institute, "account_id": "account"})
    monkeypatch.setattr(invoke.settings, "AUTO_CREATE_SCHEMA_ON_STARTUP", False)
    monkeypatch.setattr(invoke.settings, "MARKETING_ACCOUNTS_JSON", json.dumps([account.model_dump()]))
    monkeypatch.setattr(dispatch_worker, "utcnow", lambda: NOW + timedelta(microseconds=5))
    with Session(engine) as db:
        intent = dispatch_intents.prepare(db, institute, body(approval, contact), "manager")
        # Owned test schema has metadata-created tables; stamp is only a gate fixture,
        # not evidence that a production migration ran successfully.
        context = MigrationContext.configure(db.connection()); context._ensure_version_table()
        heads = ScriptDirectory(str(Path(invoke.__file__).resolve().parents[3] / "migrations")).get_heads()
        for head in heads: db.execute(text("INSERT INTO alembic_version (version_num) VALUES (:head)"), {"head": head})
        db.commit()
    declare_send(engine, institute, intent)
    adapter = Fake(engine, institute, intent)
    factory = lambda: Session(engine)
    resolver = lambda account: dispatch_worker.Binding(account, adapter)
    command = invoke.Command(institute_id=institute, intent_id=intent.id, expected_fingerprint=intent.request_fingerprint)
    return intent, adapter, factory, resolver, command


def test_postgres_invocation_inspects_then_lost_reply_reconciles_without_resubmit(postgres_flow, monkeypatch):
    engine, institute = postgres_flow[:2]
    intent, adapter, factory, resolver, command = fixture(engine, institute, monkeypatch)
    inspection = invoke.invoke(factory, command, lambda _: pytest.fail("Inspection must not resolve credentials"))
    assert inspection.operation == "inspect" and inspection.status == "unobserved" and inspection.outcome_id is None
    assert not inspection.delivery_confirmed and adapter.submits == adapter.reconciles == 0
    for patch in ({"expected_fingerprint": "0" * 64}, {"institute_id": "foreign"}, {"intent_id": "absent"}):
        with pytest.raises(HTTPException): invoke.invoke(factory, command.model_copy(update=patch), resolver)
    with Session(engine) as db:
        db.execute(text("UPDATE alembic_version SET version_num='wrong-head'")); db.commit()
    with pytest.raises(HTTPException): invoke.invoke(factory, command.model_copy(update={"execute": True}), resolver)
    with Session(engine) as db:
        head = ScriptDirectory(str(Path(invoke.__file__).resolve().parents[3] / "migrations")).get_current_head()
        db.execute(text("UPDATE alembic_version SET version_num=:head"), {"head": head}); db.commit()
    assert adapter.submits == adapter.reconciles == 0
    adapter.lose = True
    executing = command.model_copy(update={"execute": True})
    first = invoke.invoke(factory, executing, resolver)
    assert first.operation == "uncertain" and first.status == "unknown" and adapter.submits == 1
    with Session(engine) as db:
        contact_originals.create(db, institute, "aud_000", contact_body(institute, "aud_000", "invoke-withdraw", intent.request.expected_contact_id, "refused"), "manager")
    second = invoke.invoke(factory, executing, resolver)
    assert second.operation == "reconcile_observed" and second.status == "accepted"
    assert adapter.submits == adapter.reconciles == 1
    assert invoke.invoke(factory, executing, resolver).operation == "terminal"
    assert adapter.submits == adapter.reconciles == 1
    with Session(engine) as db: assert db.scalar(select(func.count()).select_from(DispatchOutcome)) == 2


def test_postgres_command_receipts_exclusive_redacted_and_failure_safe(postgres_flow, monkeypatch, tmp_path, capsys):
    engine, institute = postgres_flow[:2]
    intent, adapter, factory, resolver, command = fixture(engine, institute, monkeypatch)
    monkeypatch.setattr(session, "SessionLocal", factory)
    monkeypatch.setattr(invoke.transport_registry, "resolver", lambda _: resolver)
    args = ["--institute", institute, "--intent", intent.id, "--expected-fingerprint", intent.request_fingerprint]
    assert invoke.main(args + ["--execute"]) == 1
    assert adapter.submits == 0
    existing = tmp_path / "existing.json"; existing.write_text("unchanged", encoding="utf-8")
    assert invoke.main(args + ["--execute", "--receipt", str(existing)]) == 1
    assert existing.read_text(encoding="utf-8") == "unchanged" and adapter.submits == 0
    capsys.readouterr(); adapter.lose = True
    first = tmp_path / "first.json"
    assert invoke.main(args + ["--execute", "--receipt", str(first)]) == 2
    output = capsys.readouterr(); retained = json.loads(first.read_text(encoding="utf-8"))
    assert json.loads(output.out) == retained and output.err == "" and retained["status"] == "unknown"
    assert set(retained) == {"institute_id", "intent_id", "request_fingerprint", "mode", "operation", "status", "outcome_id", "delivery_confirmed"}
    assert "explicit@example" not in output.out and "secret" not in output.out
    second = tmp_path / "second.json"
    assert invoke.main(args + ["--execute", "--receipt", str(second)]) == 0
    assert adapter.submits == adapter.reconciles == 1
    capsys.readouterr()
    monkeypatch.setattr(invoke.os, "fsync", lambda _: (_ for _ in ()).throw(OSError("secret-destination-must-not-print")))
    assert invoke.main(args + ["--execute", "--receipt", str(tmp_path / "failed-sync.json")]) == 1
    failed = capsys.readouterr(); assert failed.out == "" and "secret-destination" not in failed.err
    assert adapter.submits == adapter.reconciles == 1


def test_postgres_invocation_refuses_withdrawal_and_auto_schema_before_io(postgres_flow, monkeypatch):
    engine, institute = postgres_flow[:2]
    intent, adapter, factory, resolver, command = fixture(engine, institute, monkeypatch)
    executing = command.model_copy(update={"execute": True})
    monkeypatch.setattr(invoke.settings, "AUTO_CREATE_SCHEMA_ON_STARTUP", True)
    with pytest.raises(HTTPException): invoke.invoke(factory, executing, resolver)
    monkeypatch.setattr(invoke.settings, "AUTO_CREATE_SCHEMA_ON_STARTUP", False)
    with Session(engine) as db:
        contact_originals.create(db, institute, "aud_000", contact_body(institute, "aud_000", "before-invoke", intent.request.expected_contact_id, "refused"), "manager")
    with pytest.raises(HTTPException): invoke.invoke(factory, executing, resolver)
    assert adapter.submits == adapter.reconciles == 0
    with Session(engine) as db: assert db.scalar(select(func.count()).select_from(DispatchOutcome)) == 0


def test_invocation_contract_rejects_coercion_and_bad_fingerprint():
    base = dict(institute_id="i", intent_id="intent", expected_fingerprint="a" * 64)
    for patch in ({"execute": 1}, {"expected_fingerprint": "A" * 64}, {"expected_fingerprint": "a" * 63}, {"execute": "true"}, {"extra": "secret"}):
        with pytest.raises(ValueError): invoke.Command(**(base | patch))


def test_sqlite_deployment_invocation_refuses_before_resolving_provider(client, monkeypatch):
    institute, _, _ = _bootstrap_reference_data(client)
    monkeypatch.setattr(invoke.settings, "AUTO_CREATE_SCHEMA_ON_STARTUP", False)
    command = invoke.Command(institute_id=institute, intent_id="unretained", expected_fingerprint="a" * 64, execute=True)
    with pytest.raises(HTTPException, match="Deployment invocation requires PostgreSQL"):
        invoke.invoke(lambda: Session(main_module.engine), command, lambda _: pytest.fail("No adapter resolution allowed"))


def test_postgres_test_mode_account_cannot_enter_deployment_execution(postgres_flow, monkeypatch):
    engine, institute = postgres_flow[:2]
    intent, adapter, factory, resolver, command = fixture(engine, institute, monkeypatch)
    # A second own customer can prepare another actual original in fixture test mode.
    from test_marketing_dispatch_intents_13ai import configure
    with Session(engine) as db:
        other_contact = contact_originals.create(db, institute, "aud_054", contact_body(institute, "aud_054", "test-mode-contact"), "manager")
        configure(institute, monkeypatch)
        payload = intent.request.model_copy(update={"customer_id": "aud_054", "expected_contact_id": other_contact.id, "idempotency_key": "test-mode-intent"})
        other = dispatch_intents.prepare(db, institute, payload, "manager")
    selected = invoke.Command(institute_id=institute, intent_id=other.id, expected_fingerprint=other.request_fingerprint, execute=True)
    with pytest.raises(HTTPException, match="explicitly live account"):
        invoke.invoke(factory, selected, lambda _: pytest.fail("Fixture account cannot reach live resolver"))
    assert adapter.submits == adapter.reconciles == 0
