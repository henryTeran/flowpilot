from datetime import timedelta
import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.marketing import dispatch_intents, campaign_originals, contact_originals
from test_marketing_dispatch_outcomes_13aj import fixture
from test_marketing_contact_originals_13y import body as contact_body
from test_marketing_send_13an import send_request
from test_crm_billing_12b import NOW
from test_postgres_scheduling_4d import postgres_flow
from test_ticket_workflow import _bootstrap_reference_data


def exercise(engine, institute, monkeypatch):
    first = fixture(engine, institute, monkeypatch)
    with Session(engine) as db:
        approval = campaign_originals.require(db, institute, first.request.expected_revision_id)
        contact = contact_originals.create(db, institute, "aud_054", contact_body(institute, "aud_054", "second-contact"), "manager")
        sent = campaign_originals.execute(db, institute, send_request(first), "manager")
        request = first.request.model_copy(update={"customer_id":"aud_054", "expected_contact_id":contact.id, "idempotency_key":"second-intent"})
        for patch in ({"expected_revision_id":sent.revision.id}, {"expected_revision_id":"foreign-approval"}):
            with pytest.raises(HTTPException): dispatch_intents.prepare(db, institute, request.model_copy(update=patch), "manager")
        with monkeypatch.context() as clock:
            clock.setattr(dispatch_intents, "utcnow", lambda: NOW + timedelta(microseconds=2))
            with pytest.raises(HTTPException): dispatch_intents.prepare(db, institute, request, "manager")
        assert dispatch_intents.original(db, institute, request.idempotency_key) is None
        refused = contact_originals.create(db, institute, "aud_054", contact_body(institute, "aud_054", "refuse-before-intent", contact.id, "refused"), "manager")
        with pytest.raises(HTTPException):
            dispatch_intents.prepare(db, institute, request.model_copy(update={"expected_contact_id":refused.id}), "manager")
        assert dispatch_intents.original(db, institute, request.idempotency_key) is None
        contact = contact_originals.create(db, institute, "aud_054", contact_body(institute, "aud_054", "renew-before-intent", refused.id), "manager")
        request = request.model_copy(update={"expected_contact_id":contact.id})
        second = dispatch_intents.prepare(db, institute, request, "manager")
        assert second.request == request and second.submission.eligibility.campaign == approval.revision
        assert dispatch_intents.require(db, institute, second.id) == second
        assert campaign_originals.current(db, institute, request.campaign_id) == sent
        withdrawn = contact_originals.create(db, institute, "aud_054", contact_body(institute, "aud_054", "withdraw", contact.id, "refused"), "manager")
        assert dispatch_intents.prepare(db, institute, request, "manager") == second
        with pytest.raises(HTTPException): dispatch_intents.prepare(db, institute, request.model_copy(update={"idempotency_key":"new-operation", "expected_contact_id":withdrawn.id}), "manager")


def test_sqlite_preparation_after_send_retains_exact_approval(client, monkeypatch):
    institute, _, _ = _bootstrap_reference_data(client); exercise(main_module.engine, institute, monkeypatch)


def test_postgres_preparation_after_send_retains_exact_approval(postgres_flow, monkeypatch):
    exercise(postgres_flow[0], postgres_flow[1], monkeypatch)
