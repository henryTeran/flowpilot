"""Explicit pytest exporter for native contract vectors; isolated SQLite, no provider I/O."""
import json
from datetime import timedelta
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.marketing import audience_originals, campaign_originals, dispatch_intents, dispatch_outcomes, provider, dispatch_catalogs
from test_marketing_recipient_observations_13z import setup
from test_marketing_dispatch_intents_13ai import configure, body as intent_body
from test_marketing_campaign_originals_13i import body as campaign_body
from test_ticket_workflow import _bootstrap_reference_data
from test_crm_billing_12b import NOW


def test_export_native_dispatch_vectors(client, monkeypatch):
    institute, _, _ = _bootstrap_reference_data(client)
    _, _, contact = setup(main_module.engine, institute, monkeypatch); configure(institute, monkeypatch)
    for module in (audience_originals, campaign_originals): monkeypatch.setattr(module, "utcnow", lambda: NOW + timedelta(microseconds=4))
    monkeypatch.setattr(dispatch_outcomes, "utcnow", lambda: NOW + timedelta(microseconds=5))
    vectors = []
    with Session(main_module.engine) as db:
        for channel in ("email", "sms", "push"):
            capture = audience_originals.create(db, institute, audience_originals.ContactRequest(segments=("NEW",), channel=channel,
                permission_basis="marketing_contact", reason="Explicit native dispatch vector", idempotency_key="vector-capture-" + channel), "manager")
            content = campaign_originals.Content(channel=channel, origin="ai", subject="Subject" if channel == "email" else None,
                body="Literal \u00e9 \U0001f642 \x7f {customer_name}", audience_id=capture.id, template_original_id=None)
            draft = campaign_originals.execute(db, institute, campaign_body(capture.id, "vector-draft-" + channel, content=content), "manager")
            review = campaign_originals.execute(db, institute, campaign_body(capture.id, "vector-review-" + channel, draft.revision.campaign_id, draft.revision.id, "review"), "manager")
            approved = campaign_originals.execute(db, institute, campaign_body(capture.id, "vector-approve-" + channel, draft.revision.campaign_id, review.revision.id, "approve"), "manager")
            account = provider.Account(institute_id=institute, provider="fixture-only", account_id="vector-account-" + channel,
                channel=channel, sender_id="fixture-sender", mode="test", push_application="institute-app" if channel == "push" else None)
            monkeypatch.setattr(dispatch_intents.settings, "MARKETING_ACCOUNTS_JSON", json.dumps([account.model_dump()]))
            intent = dispatch_intents.prepare(db, institute, intent_body(approved, contact, "vector-intent-" + channel).model_copy(update={"account_id":account.account_id}), "manager")
            previous = None
            for index, status in enumerate(("unknown", "accepted")):
                result = provider.Result(account=account, idempotency_key=intent.request.idempotency_key, request_fingerprint=intent.request_fingerprint,
                    status=status, provider_message_id="fixture-reference" if status == "accepted" else None, observed_at=NOW + timedelta(microseconds=4 + index))
                outcome = dispatch_outcomes.append(db, institute, dispatch_outcomes.Request(intent_id=intent.id, expected_previous_id=previous,
                    result=result, reason="Explicit simulated vector observation", idempotency_key=f"vector-outcome-{channel}-{index}"), "fixture-worker")
                previous = outcome.id
            vectors.append(dict(institute_id=institute, account_page=dispatch_catalogs.accounts(db, institute, channel).model_dump(mode="json"),
                approval=approved.model_dump(mode="json"), contact=contact.model_dump(mode="json"), intent=intent.model_dump(mode="json"),
                intent_page=dispatch_catalogs.intents(db, institute, approved.revision.campaign_id).model_dump(mode="json"),
                outcome=outcome.model_dump(mode="json"), outcome_page=dispatch_outcomes.audit(db, institute, intent.id).model_dump(mode="json")))
    print("FLOWPILOT_EXPORT=" + json.dumps(vectors, ensure_ascii=True, separators=(",", ":")))
