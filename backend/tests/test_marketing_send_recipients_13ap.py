from datetime import timedelta
import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.marketing import campaign_originals, recipient_observations, contact_originals
from test_marketing_recipient_observations_13z import setup
from test_marketing_campaign_originals_13i import body as campaign_body
from test_marketing_contact_originals_13y import body as contact_body
from test_postgres_scheduling_4d import postgres_flow
from test_crm_billing_12b import NOW
from test_ticket_workflow import _bootstrap_reference_data, _auth_headers


def exercise(engine, institute, monkeypatch):
    audience, approval, contact = setup(engine, institute, monkeypatch)
    monkeypatch.setattr(recipient_observations, "utcnow", lambda: NOW + timedelta(microseconds=5))
    with Session(engine) as db:
        sent = campaign_originals.execute(db, institute, campaign_body(audience.id, "send", approval.revision.campaign_id, approval.revision.id, "send"), "manager")
        with pytest.raises(HTTPException): recipient_observations.read(db, institute, approval.revision.campaign_id, approval.revision.id)
        page = recipient_observations.read(db, institute, sent.revision.campaign_id, sent.revision.id, 0, 1)
        assert page.campaign == sent and page.total == 2 and page.items[0].original == contact
        assert page.items[0].reason == "declared_eligible" and page.items[0].eligible_by_current_declaration
        assert not page.delivery_authorized and not page.external_message_sent and not page.complete_campaign_evaluation
        assert recipient_observations.Page.model_validate_json(page.model_dump_json()) == page
        withdrawal = contact_originals.create(db, institute, "aud_000", contact_body(institute, "aud_000", "withdraw", contact.id, "refused"), "manager")
        fresh = recipient_observations.read(db, institute, sent.revision.campaign_id, sent.revision.id, 0, 1)
        assert fresh.items[0].original == withdrawal and fresh.items[0].reason == "permission_refused" and not fresh.items[0].eligible_by_current_declaration
        assert campaign_originals.current(db, institute, sent.revision.campaign_id) == sent
        assert campaign_originals.require(db, institute, approval.revision.id) == approval
        assert contact_originals.require(db, institute, "aud_000", contact.id) == contact
        return sent


def test_sqlite_send_recipient_observation_and_signed_read(client, monkeypatch):
    institute, _, _ = _bootstrap_reference_data(client); sent = exercise(main_module.engine, institute, monkeypatch)
    path = f"/api/v1/marketing/institutes/{institute}/campaigns/{sent.revision.campaign_id}/recipient-observations?expected_revision_id={sent.revision.id}&limit=1"
    response = client.get(path, headers=_auth_headers("responsable_institut", institute))
    assert response.status_code == 200 and response.json()["items"][0]["reason"] == "permission_refused"
    assert client.get(path, headers=_auth_headers("accueil", institute)).status_code == 403
    assert client.get(path, headers=_auth_headers("responsable_institut", "foreign")).status_code == 403


def test_postgres_send_recipient_observation(postgres_flow, monkeypatch):
    exercise(postgres_flow[0], postgres_flow[1], monkeypatch)
