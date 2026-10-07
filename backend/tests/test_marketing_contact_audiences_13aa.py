from datetime import timedelta
import copy

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

import app.main as main_module
from app.modules.marketing import audience_originals as audiences, contact_originals as contacts, campaign_originals as campaigns
from app.modules.marketing.models import AudiencePage
from test_crm_billing_12b import NOW
from test_marketing_audience_originals_13e import exercise as legacy_fixture
from test_marketing_contact_originals_13y import body as contact_body
from test_marketing_campaign_originals_13i import body as campaign_body
from test_postgres_scheduling_4d import postgres_flow
from test_ticket_workflow import _auth_headers, _bootstrap_reference_data


def request(channel, key=None):
    return audiences.ContactRequest(segments=("NEW",), channel=channel, permission_basis="marketing_contact",
        reason="Explicit current contact audience", idempotency_key=key or f"contact-audience-{channel}")


def exercise(engine, institute, monkeypatch):
    legacy = legacy_fixture(engine, institute, monkeypatch)
    monkeypatch.setattr(contacts, "utcnow", lambda: NOW + timedelta(microseconds=3))
    monkeypatch.setattr(audiences, "utcnow", lambda: NOW + timedelta(microseconds=4))
    monkeypatch.setattr(campaigns, "utcnow", lambda: NOW + timedelta(microseconds=4))
    with Session(engine) as db:
        legacy_pages = [audiences.page(db, institute, legacy.id, i).model_dump_json() for i in range(2)]
        originals = {c: contacts.create(db, institute, c, contact_body(institute, c, f"contacts-{c}"), "manager") for c in ("aud_000", "aud_054")}
        captured = {}
        for channel in ("email", "sms", "push"):
            cap = audiences.create(db, institute, request(channel), "manager"); captured[channel] = cap
            assert cap.request.permission_basis == "marketing_contact" and cap.summary.customer_count == 55
            assert cap.summary.eligible_count == 2 and cap.summary.page_count == 2
            first, last = (audiences.page(db, institute, cap.id, i) for i in range(2))
            assert len(first.observation.items) == 50 and len(last.observation.items) == 5
            assert first.observation.captured_at == last.observation.captured_at == cap.captured_at
            assert first.observation.items[0].declaration == originals["aud_000"]
            assert last.observation.items[-1].declaration == originals["aud_054"]
            assert first.observation.items[1].marketing_permission == "unknown"  # No legacy fallback.
            recipient = audiences.campaign_audience(db, institute, cap.id, channel)
            assert recipient.customer_ids == ("aud_000", "aud_054")
            content = campaigns.Content(channel=channel, origin="ai", subject="Email subject" if channel == "email" else None,
                body="Literal approved channel content", audience_id=cap.id, template_original_id=None)
            draft = campaigns.execute(db, institute, campaign_body(cap.id, f"draft-{channel}", content=content), "manager")
            root = draft.revision.campaign_id
            review = campaigns.execute(db, institute, campaign_body(cap.id, f"review-{channel}", root, draft.revision.id, "review"), "manager")
            approved = campaigns.execute(db, institute, campaign_body(cap.id, f"approve-{channel}", root, review.revision.id, "approve"), "manager")
            assert approved.revision.state == "APPROVE" and approved.revision.content.channel == channel
            assert not approved.revision.delivery_authorized and not approved.revision.external_message_sent
            value = first.model_dump()
            bad = copy.deepcopy(value); bad["observation"]["items"][0]["declaration"]["declaration"]["customer_id"] = "foreign"
            with pytest.raises(ValidationError): audiences.RetainedPage.model_validate(bad)
            bad = copy.deepcopy(value); bad["observation"]["items"][0]["marketing_permission"] = "unknown"
            with pytest.raises(ValidationError): audiences.RetainedPage.model_validate(bad)
        with pytest.raises(HTTPException): audiences.create(db, institute, request("email", "capture"), "manager")
        monkeypatch.setattr(contacts, "utcnow", lambda: NOW + timedelta(microseconds=5))
        contacts.create(db, institute, "aud_054", contact_body(institute, "aud_054", "withdraw", originals["aud_054"].id, "refused"), "manager")
        for cap in captured.values():
            assert audiences.create(db, institute, cap.request, "manager") == cap
            assert audiences.campaign_audience(db, institute, cap.id, cap.request.channel).customer_ids == ("aud_000", "aud_054")
        future = audiences.create(db, institute, request("push", "future"), "manager")
        assert future.summary.eligible_count == 1
        assert audiences.page(db, institute, future.id, 1).observation.items[-1].marketing_permission == "future_declaration"
        monkeypatch.setattr(audiences, "utcnow", lambda: NOW + timedelta(microseconds=6))
        changed = audiences.create(db, institute, request("push", "withdrawn"), "manager")
        assert changed.summary.eligible_count == 1
        assert audiences.page(db, institute, changed.id, 1).observation.items[-1].marketing_permission == "refused"
        assert [audiences.page(db, institute, legacy.id, i).model_dump_json() for i in range(2)] == legacy_pages
        # A retained page cannot silently change its permission source basis.
        row = db.get(AudiencePage, (institute, captured["push"].id, 0))
        wrong = copy.deepcopy(row.observation); wrong["selection"].pop("permission_basis"); row.observation = wrong
        with pytest.raises((HTTPException, ValidationError)): audiences.page(db, institute, captured["push"].id, 0)
        db.rollback()
        return captured["push"]


def test_sqlite_contact_capture_all_channels_legacy_replay_and_signed_routes(client, monkeypatch):
    institute, _, _ = _bootstrap_reference_data(client)
    capture = exercise(main_module.engine, institute, monkeypatch)
    path = f"/api/v1/marketing/institutes/{institute}"
    headers = _auth_headers("responsable_institut", institute)
    reply = client.post(path + "/audience-captures", json=request("push", "http").model_dump(mode="json"), headers=headers)
    assert reply.status_code == 200, reply.text
    assert reply.json()["request"]["permission_basis"] == "marketing_contact"
    value = reply.json()
    page = client.get(path + f"/audience-captures/{value['id']}/pages/0", headers=headers)
    assert page.status_code == 200 and page.json()["observation"]["selection"]["permission_basis"] == "marketing_contact"
    assert client.get(path + "/audience-captures/original/http", headers=headers).json() == value
    observed = client.post(path + "/audience-observations", json={"segments": ["NEW"], "channel": "push", "after": None,
        "permission_basis": "marketing_contact"}, headers=headers)
    assert observed.status_code == 200 and observed.json()["selection"]["permission_basis"] == "marketing_contact"
    for role, owner in [("accueil", institute), ("collaboratrice", institute), ("responsable_institut", "foreign")]:
        assert client.post(path + "/audience-captures", json=request("push", "denied").model_dump(mode="json"), headers=_auth_headers(role, owner)).status_code == 403


def test_postgres_contact_capture_all_channels_and_legacy_history(postgres_flow, monkeypatch):
    exercise(postgres_flow[0], postgres_flow[1], monkeypatch)
