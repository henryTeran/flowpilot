from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import copy
import pytest
from fastapi import HTTPException
from sqlalchemy import event, select, func
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.marketing import campaign_originals as campaigns, dispatch_worker, dispatch_outcomes
from app.modules.marketing.models import CampaignOriginal, CampaignHead
from test_marketing_dispatch_outcomes_13aj import fixture
from test_marketing_dispatch_worker_13ak import Fake
from test_postgres_scheduling_4d import postgres_flow
from test_crm_billing_12b import NOW
from test_ticket_workflow import _bootstrap_reference_data, _auth_headers


def send_request(intent, key="send"):
    return campaigns.Request(action="send", campaign_id=intent.request.campaign_id,
        expected_revision_id=intent.request.expected_revision_id, content=None,
        reason="Manager explicitly declares SEND", idempotency_key=key)


def exercise(engine, institute, monkeypatch):
    intent = fixture(engine, institute, monkeypatch)
    monkeypatch.setattr(dispatch_worker, "utcnow", lambda: NOW + timedelta(microseconds=5))
    adapter = Fake(engine, institute, intent)
    run = lambda: dispatch_worker.run(lambda: Session(engine), institute, intent.id, "worker", lambda account: dispatch_worker.Binding(account, adapter))
    # Approval alone must no longer produce an attempt or decision marker.
    with pytest.raises(HTTPException): run()
    assert adapter.submits == adapter.reconciles == 0
    with Session(engine) as db:
        assert dispatch_outcomes.current(db, institute, intent.id) is None
        request = send_request(intent)
        approval = campaigns.require(db, institute, intent.request.expected_revision_id)
        def fail(session, context, instances):
            if any(isinstance(row, CampaignHead) for row in session.dirty): raise RuntimeError("Injected SEND head failure")
        event.listen(db, "before_flush", fail)
        try:
            with pytest.raises(RuntimeError): campaigns.execute(db, institute, request, "manager")
        finally: event.remove(db, "before_flush", fail)
        assert campaigns.original(db, institute, "send") is None and campaigns.current(db, institute, request.campaign_id) == approval
        sent = campaigns.execute(db, institute, request, "manager")
        assert sent.revision.state == "SEND" and sent.revision.previous_id == approval.revision.id
        assert sent.revision.content == approval.revision.content
        assert not sent.revision.external_message_sent and not sent.revision.delivery_authorized
        assert campaigns.require(db, institute, approval.revision.id) == approval
        assert campaigns.audit(db, institute, request.campaign_id).total == 4
        for payload, actor in [(request.model_copy(update={"idempotency_key":"duplicate"}), "manager"),
                (request, "other"), (request.model_copy(update={"reason":"Changed terms"}), "manager"),
                (request.model_copy(update={"action":"edit", "expected_revision_id":sent.revision.id,
                    "idempotency_key":"edit-sent", "content": campaigns.Content(channel="email", origin="ai",
                    subject="New", body="Changed", audience_id=approval.revision.content.audience.id, template_original_id=None)}), "manager")]:
            with pytest.raises(HTTPException): campaigns.execute(db, institute, payload, actor)
        # Original replay precedes a now-invalid clock/current stage.
        with monkeypatch.context() as clock:
            clock.setattr(campaigns, "utcnow", lambda: NOW - timedelta(days=1))
            assert campaigns.execute(db, institute, request, "manager") == sent
        assert campaigns.current(db, institute, request.campaign_id) == sent
    assert run().outcome.request.result.status == "accepted" and adapter.submits == 1
    assert run().operation == "terminal" and adapter.submits == 1
    # Raw corruption cannot turn a different approval into authority.
    with Session(engine) as db:
        row = db.get(CampaignOriginal, sent.revision.id)
        value = copy.deepcopy(row.revision); value["content"]["body"] = "Tampered"
        from app.modules.marketing.campaigns import CampaignContent, digest
        value["reviewed_digest"] = value["approved_digest"] = digest(CampaignContent.model_validate(value["content"]))
        row.revision = value; db.commit()
        with pytest.raises(HTTPException): campaigns.require(db, institute, sent.revision.id)
    return intent


def test_sqlite_signed_send_and_first_decision_require_authority(client, monkeypatch):
    institute, _, _ = _bootstrap_reference_data(client)
    exercise(main_module.engine, institute, monkeypatch)


def test_postgres_send_retention_and_worker_authorization(postgres_flow, monkeypatch):
    exercise(postgres_flow[0], postgres_flow[1], monkeypatch)


def test_signed_http_send_actor_replay_and_roles(client, monkeypatch):
    institute, _, _ = _bootstrap_reference_data(client)
    intent = fixture(main_module.engine, institute, monkeypatch)
    path = f"/api/v1/marketing/institutes/{institute}/campaigns"
    payload = send_request(intent).model_dump(mode="json")
    for role, owner in [("accueil", institute), ("collaboratrice", institute), ("responsable_institut", "foreign")]:
        assert client.post(path, json=payload, headers=_auth_headers(role, owner)).status_code == 403
    assert client.post(path, json=payload).status_code == 403
    headers = _auth_headers("responsable_institut", institute)
    reply = client.post(path, json=payload, headers=headers)
    assert reply.status_code == 200
    sent = reply.json(); assert sent["revision"]["state"] == "SEND" and sent["revision"]["actor_id"] == "test-user"
    assert client.post(path, json=payload, headers=headers).json() == sent
    assert client.get(path + "/original/send", headers=headers).json() == sent
    assert client.get(path + "/" + sent["revision"]["id"], headers=headers).json() == sent
    assert client.get(path + "/" + sent["revision"]["campaign_id"] + "/current", headers=headers).json() == sent
    assert client.get(path + "?offset=0&limit=20", headers=headers).json()["items"] == [sent]
    assert client.post(path, json={**payload, "idempotency_key":"again"}, headers=headers).status_code == 400


def test_postgres_competing_send_keys_create_one_authority(postgres_flow, monkeypatch):
    engine, institute = postgres_flow[:2]; intent = fixture(engine, institute, monkeypatch)
    def run(key):
        with Session(engine) as db:
            try: return campaigns.execute(db, institute, send_request(intent, key), "manager")
            except HTTPException as error:
                assert error.status_code == 400
                return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [f.result(timeout=20) for f in [pool.submit(run, key) for key in ("send-one", "send-two")]]
    assert sum(value is not None for value in results) == 1
    with Session(engine) as db:
        assert campaigns.current(db, institute, intent.request.campaign_id) == next(value for value in results if value is not None)
        assert db.scalar(select(func.count()).select_from(CampaignOriginal).where(CampaignOriginal.campaign_id == intent.request.campaign_id)) == 4
