from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
import pytest
from fastapi import HTTPException
from sqlalchemy import event, select, func
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.marketing import dispatch_intents as service, contact_originals
from app.modules.marketing import audience_originals, campaign_originals
from app.modules.marketing.models import DispatchIntent
from test_marketing_recipient_observations_13z import setup
from test_marketing_contact_originals_13y import body as contact_body
from test_crm_billing_12b import NOW
from test_postgres_scheduling_4d import postgres_flow
from test_ticket_workflow import _auth_headers, _bootstrap_reference_data
from test_marketing_campaign_originals_13i import body as campaign_body

def configure(institute, monkeypatch):
    monkeypatch.setattr(service.settings, "MARKETING_ACCOUNTS_JSON", json.dumps([dict(institute_id=institute, provider="test-only", account_id="account",
        channel="email", sender_id="sender", mode="test", push_application=None)]))
    monkeypatch.setattr(service, "utcnow", lambda: NOW + timedelta(microseconds=4))

def body(approval, contact, key="intent"):
    return service.Request(campaign_id=approval.revision.campaign_id, expected_revision_id=approval.revision.id, customer_id="aud_000",
        expected_contact_id=contact.id, account_id="account", reason="Explicit approved recipient preparation", idempotency_key=key)

def exercise(engine, institute, monkeypatch):
    _, approval, contact = setup(engine, institute, monkeypatch); configure(institute, monkeypatch)
    payload = body(approval, contact)
    with Session(engine) as db:
        for change in ({"expected_revision_id": "stale"}, {"expected_contact_id": "stale"}, {"customer_id": "aud_054"}, {"account_id": "absent"}):
            with pytest.raises(HTTPException): service.prepare(db, institute, payload.model_copy(update=change), "manager")
        monkeypatch.setattr(service, "utcnow", lambda: NOW)
        with pytest.raises(HTTPException): service.prepare(db, institute, payload, "manager")
        configure(institute, monkeypatch)
        for config in ("[]", "not-json", "{}", service.settings.MARKETING_ACCOUNTS_JSON[:-1] + "," + service.settings.MARKETING_ACCOUNTS_JSON[1:]):
            with monkeypatch.context() as guarded:
                guarded.setattr(service.settings, "MARKETING_ACCOUNTS_JSON", config)
                with pytest.raises(HTTPException): service.prepare(db, institute, payload, "manager")
        def fail(session, context, instances):
            if any(isinstance(r, DispatchIntent) for r in session.new): raise RuntimeError("Injected intent failure")
        event.listen(db, "before_flush", fail)
        try:
            with pytest.raises(RuntimeError): service.prepare(db, institute, payload, "manager")
        finally: event.remove(db, "before_flush", fail)
        assert service.original(db, institute, "intent") is None
        original = service.prepare(db, institute, payload, "manager")
        assert service.original(db, institute, "intent") == original and service.require(db, institute, original.id) == original
        assert original.submission.eligibility.original == contact
        assert not original.submission.eligibility.delivery_authorized
        for altered, actor in [(payload, "other"), (payload.model_copy(update={"reason": "Other reason"}), "manager"),
                (body(approval, contact, "duplicate"), "manager")]:
            with pytest.raises(HTTPException): service.prepare(db, institute, altered, actor)
        withdrawn = contact_originals.create(db, institute, "aud_000", contact_body(institute, "aud_000", "withdraw-intent", contact.id, "refused"), "manager")
        def fail_current(*args): raise AssertionError("Historical replay consulted current sources/config/clock")
        with monkeypatch.context() as guarded:
            guarded.setattr(service, "utcnow", fail_current); guarded.setattr(service, "configured", fail_current)
            guarded.setattr(service.campaign_originals, "current", fail_current); guarded.setattr(service.contact_originals, "current", fail_current)
            assert service.prepare(db, institute, payload, "manager") == original
        with pytest.raises(HTTPException): service.prepare(db, institute, body(approval, withdrawn, "withdrawn"), "manager")
        row = db.get(DispatchIntent, original.id); prior = row.request_fingerprint; row.request_fingerprint = "0" * 64; db.commit()
        with pytest.raises(HTTPException): service.require(db, institute, original.id)
        row.request_fingerprint = prior; db.commit()
        assert db.scalar(select(func.count()).select_from(DispatchIntent)) == 1
    return payload, original

def test_sqlite_preparation_recovery_atomicity_and_signed_routes(client, monkeypatch):
    institute, _, _ = _bootstrap_reference_data(client)
    payload, original = exercise(main_module.engine, institute, monkeypatch)
    path = f"/api/v1/marketing/institutes/{institute}/dispatch-intents"; headers = _auth_headers("responsable_institut", institute)
    assert client.get(path + "/original/intent", headers=headers).json()["id"] == original.id
    assert client.get(path + "/" + original.id, headers=headers).status_code == 200
    assert client.post(path, json=payload.model_dump(mode="json"), headers=headers).status_code == 400  # signed actor differs
    for role, owner in [("accueil", institute), ("collaboratrice", institute), ("responsable_institut", "foreign")]:
        h = _auth_headers(role, owner)
        assert client.post(path, json=payload.model_dump(mode="json"), headers=h).status_code == 403
        assert client.get(path + "/original/intent", headers=h).status_code == 403
    assert client.post(path, json={**payload.model_dump(mode="json"), "actor_id": "forged"}, headers=headers).status_code == 422
    assert client.get(path + "/original/intent").status_code == 403

def test_postgres_preparation_recovery(postgres_flow, monkeypatch): exercise(postgres_flow[0], postgres_flow[1], monkeypatch)

@pytest.mark.parametrize("distinct_keys", [False, True])
def test_postgres_same_key_preparation_serializes(postgres_flow, monkeypatch, distinct_keys):
    engine, institute = postgres_flow[:2]; _, approval, contact = setup(engine, institute, monkeypatch); configure(institute, monkeypatch)
    payload = body(approval, contact)
    def run(index):
        request = payload.model_copy(update={"idempotency_key": f"intent-{index}"}) if distinct_keys else payload
        with Session(engine) as db:
            try: return service.prepare(db, institute, request, "manager")
            except HTTPException as error: return error.status_code
    with ThreadPoolExecutor(max_workers=2) as pool: a, b = list(pool.map(run, range(2)))
    if distinct_keys: assert sum(v == 400 for v in (a, b)) == 1
    else: assert a == b
    with Session(engine) as db: assert db.scalar(select(func.count()).select_from(DispatchIntent)) == 1

def test_signed_preparation_has_key_id_receipt_and_replays_without_configuration(client, monkeypatch):
    institute, _, _ = _bootstrap_reference_data(client)
    _, approval, contact = setup(main_module.engine, institute, monkeypatch); configure(institute, monkeypatch)
    path = f"/api/v1/marketing/institutes/{institute}/dispatch-intents"; headers = _auth_headers("responsable_institut", institute)
    payload = body(approval, contact)
    response = client.post(path, headers=headers, json=payload.model_dump(mode="json")); assert response.status_code == 200, response.text
    original = response.json(); assert original["submission"]["actor_id"] == "test-user"
    assert client.get(path + "/original/intent", headers=headers).json() == original
    assert client.get(path + "/" + original["id"], headers=headers).json() == original
    monkeypatch.setattr(service.settings, "MARKETING_ACCOUNTS_JSON", "[]")
    assert client.post(path, headers=headers, json=payload.model_dump(mode="json")).json() == original
    assert client.post(path, headers=headers, json={**payload.model_dump(mode="json"), "reason": "Other reason"}).status_code == 400

def test_postgres_channels_and_current_withdrawal_before_any_intent(postgres_flow, monkeypatch):
    engine, institute = postgres_flow[:2]; _, first_approval, first_contact = setup(engine, institute, monkeypatch); configure(institute, monkeypatch)
    monkeypatch.setattr(audience_originals, "utcnow", lambda: NOW + timedelta(microseconds=4))
    monkeypatch.setattr(campaign_originals, "utcnow", lambda: NOW + timedelta(microseconds=4))
    with Session(engine) as db:
        refused = contact_originals.create(db, institute, "aud_000", contact_body(institute, "aud_000", "first-refusal", first_contact.id, "refused"), "manager")
        with pytest.raises(HTTPException): service.prepare(db, institute, body(first_approval, refused), "manager")
        assert db.scalar(select(func.count()).select_from(DispatchIntent)) == 0
        granted = contact_originals.create(db, institute, "aud_000", contact_body(institute, "aud_000", "renewed-grant", refused.id), "manager")
        for channel in ("email", "sms", "push"):
            cap = audience_originals.create(db, institute, audience_originals.ContactRequest(segments=("NEW",), channel=channel, permission_basis="marketing_contact",
                reason="Explicit channel preparation source", idempotency_key="prepare-cap-" + channel), "manager")
            content = campaign_originals.Content(channel=channel, origin="ai", subject="Subject" if channel == "email" else None, body="Literal approved message",
                audience_id=cap.id, template_original_id=None)
            draft = campaign_originals.execute(db, institute, campaign_body(cap.id, "prepare-draft-" + channel, content=content), "manager")
            review = campaign_originals.execute(db, institute, campaign_body(cap.id, "prepare-review-" + channel, draft.revision.campaign_id, draft.revision.id, "review"), "manager")
            approval = campaign_originals.execute(db, institute, campaign_body(cap.id, "prepare-approve-" + channel, draft.revision.campaign_id, review.revision.id, "approve"), "manager")
            account = dict(institute_id=institute, provider="test-only", account_id="account", channel=channel, sender_id="sender", mode="test",
                push_application="institute-app" if channel == "push" else None)
            monkeypatch.setattr(service.settings, "MARKETING_ACCOUNTS_JSON", json.dumps([account]))
            original = service.prepare(db, institute, body(approval, granted, "prepare-intent-" + channel), "manager")
            assert original.submission.account.channel == channel
            assert original.submission.eligibility.original == granted
        assert db.scalar(select(func.count()).select_from(DispatchIntent)) == 3
