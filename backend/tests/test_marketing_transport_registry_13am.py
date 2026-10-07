from datetime import timedelta
import json
import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.marketing import transport_registry as registry, dispatch_intents, dispatch_outcomes, dispatch_worker, provider, transports
from test_marketing_transports_13al import request, Wire, EMAIL_ID
from test_marketing_recipient_observations_13z import setup
from test_marketing_dispatch_intents_13ai import configure, body
from test_crm_billing_12b import NOW
from test_ticket_workflow import _bootstrap_reference_data

def entry(account):
    return dict(institute_id=account.institute_id, provider=account.provider, account_id=account.account_id, mode="live",
        secret_env="FLOWPILOT_MARKETING_TOKEN", expires_at_env="FLOWPILOT_MARKETING_EXPIRY" if account.provider == "fcm" else None)

@pytest.mark.parametrize("channel", ["email", "sms", "push"])
def test_registry_selects_exact_account_without_io_and_hides_secret(channel, monkeypatch):
    req = request(channel); monkeypatch.setattr(registry.settings, "MARKETING_CREDENTIAL_BINDINGS_JSON", json.dumps([entry(req.account)]))
    monkeypatch.setattr(registry, "utcnow", lambda: NOW)
    wire = Wire({}); env = {"FLOWPILOT_MARKETING_TOKEN": "registry-secret", "FLOWPILOT_MARKETING_EXPIRY": (NOW + timedelta(minutes=5)).isoformat()}
    resolve = registry.resolver(lambda: None, transport=wire, environment=env)
    binding = resolve(req.account); assert binding.account == req.account and wire.calls == []
    assert "registry-secret" not in repr(binding)
    for patch in ({"institute_id": "other"}, {"account_id": "other"}, {"mode": "test"}):
        with pytest.raises(HTTPException): resolve(req.account.model_copy(update=patch))
    env["FLOWPILOT_MARKETING_TOKEN"] = "rotated-secret"
    assert resolve(req.account).adapter._credential.value == "rotated-secret" and wire.calls == []
    del env["FLOWPILOT_MARKETING_TOKEN"]
    with pytest.raises(HTTPException): resolve(req.account)

def test_invalid_ambiguous_or_unrelated_secret_configuration_refuses(monkeypatch):
    account = request("email").account; e = entry(account)
    for value in ("not-json", "{}", json.dumps([e, e]), json.dumps([{**e, "secret_env": "SECRET_KEY"}]),
            json.dumps([{**e, "credential": "inline-secret"}]), json.dumps([{**e, "expires_at_env": "FLOWPILOT_MARKETING_EXPIRY"}])):
        monkeypatch.setattr(registry.settings, "MARKETING_CREDENTIAL_BINDINGS_JSON", value)
        with pytest.raises(HTTPException): registry.resolver(lambda: None, transport=Wire({}), environment={})(account)

def test_fcm_expiry_must_be_aware_and_cover_deadline(monkeypatch):
    account = request("push").account; monkeypatch.setattr(registry.settings, "MARKETING_CREDENTIAL_BINDINGS_JSON", json.dumps([entry(account)]))
    monkeypatch.setattr(registry, "utcnow", lambda: NOW)
    for expiry in (None, "2026-10-07", NOW.isoformat(), (NOW + timedelta(seconds=15)).isoformat()):
        env = {"FLOWPILOT_MARKETING_TOKEN": "secret", "FLOWPILOT_MARKETING_EXPIRY": expiry}
        with pytest.raises(HTTPException): registry.resolver(lambda: None, transport=Wire({}), environment=env)(account)

def test_explicit_falsy_transport_never_falls_back_to_network(monkeypatch):
    class FalsyWire(Wire):
        def __bool__(self): return False
    req = request("email"); wire = FalsyWire({"id": EMAIL_ID})
    def forbidden(*args, **kwargs): raise AssertionError("Unexpected real HTTPS fallback")
    monkeypatch.setattr(transports, "Https", forbidden)
    adapter = transports.bind(req.account, transports.Credential("fake-secret"), transport=wire).adapter
    assert adapter.submit(req).status == "accepted" and len(wire.calls) == 1

def test_registry_reads_only_reference_bound_to_exact_retained_intent(client, monkeypatch):
    institute, _, _ = _bootstrap_reference_data(client); _, approval, contact = setup(main_module.engine, institute, monkeypatch); configure(institute, monkeypatch)
    account = provider.Account(institute_id=institute, provider="resend", account_id="account", channel="email", sender_id="sender@example.com", mode="live", push_application=None)
    monkeypatch.setattr(registry.settings, "MARKETING_ACCOUNTS_JSON", json.dumps([account.model_dump()]))
    monkeypatch.setattr(registry.settings, "MARKETING_CREDENTIAL_BINDINGS_JSON", json.dumps([entry(account)]))
    for module in (dispatch_worker, dispatch_outcomes, transports, registry): monkeypatch.setattr(module, "utcnow", lambda: NOW + timedelta(microseconds=5))
    with Session(main_module.engine) as db:
        intent = dispatch_intents.prepare(db, institute, body(approval, contact), "manager")
        pending = provider.Result(account=account, idempotency_key=intent.submission.idempotency_key, request_fingerprint=intent.request_fingerprint,
            status="unknown", provider_message_id=EMAIL_ID, observed_at=NOW + timedelta(microseconds=5))
        dispatch_outcomes.append(db, institute, dispatch_outcomes.Request(intent_id=intent.id, expected_previous_id=None, result=pending,
            reason="Trusted prior provider reference", idempotency_key="reference-observation"), "worker")
    wire = Wire({"id": EMAIL_ID, "from": account.sender_id, "to": ["customer@example.com"], "subject": intent.submission.eligibility.campaign.content.subject,
        "text": intent.submission.eligibility.campaign.content.body})
    factory = lambda: Session(main_module.engine)
    resolve = registry.resolver(factory, transport=wire, environment={"FLOWPILOT_MARKETING_TOKEN": "fake-secret"})
    execution = dispatch_worker.run(factory, institute, intent.id, "worker", resolve)
    assert execution.operation == "reconcile_observed" and execution.outcome.request.result.status == "accepted"
    assert len(wire.calls) == 1 and wire.calls[0][0] == "GET"
    binding = resolve(account)
    for patch in ({"idempotency_key": "unretained"}, {"actor_id": "forged"}):
        forged = intent.submission.model_copy(update=patch)
        with pytest.raises(HTTPException): binding.adapter.reconcile(forged)
    assert len(wire.calls) == 1
