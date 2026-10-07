from datetime import timedelta
import json
from pathlib import Path
import pytest
from app.modules.marketing import conversions, campaign_originals, dispatch_intents, dispatch_outcomes, provider
from app.modules.crm.metrics import BillingWindow, ClosedTicketFact

# Exact intent/outcome projection from export_marketing_dispatch_13ar.py's retained
# three-channel vectors. SEND and billing sources below are explicit synthetic facts.
VECTORS = json.loads((Path(__file__).resolve().parent / "fixtures/marketing-conversions-13aw.json").read_text(encoding="utf-8"))


def source(channel=0):
    vector = VECTORS[channel]
    intent = dispatch_intents.Original.model_validate(vector["intent"])
    accepted = dispatch_outcomes.Original.model_validate(vector["outcome"])
    approval = intent.submission.eligibility.campaign
    at = accepted.request.result.observed_at
    authorization = campaign_originals.Original(request=campaign_originals.Request(action="send", campaign_id=approval.campaign_id,
        expected_revision_id=approval.id, content=None, reason="Explicit SEND fixture", idempotency_key="conversion-send"),
        revision=approval.model_copy(update={"id": "conversion-send", "previous_id": approval.id, "state": "SEND",
            "reason": "Explicit SEND fixture", "created_at": at}))
    captured = accepted.created_at + timedelta(days=3)
    ticket = ClosedTicketFact(institute_id=intent.submission.account.institute_id, customer_id=intent.request.customer_id, ticket_id="paid-ticket",
        closed_at=at + timedelta(days=1), captured_at=captured, currency="CHF", amount_minor="12345", amount_quality="known")
    window = BillingWindow(institute_id=ticket.institute_id, customer_id=ticket.customer_id,
        start=at, end=at + timedelta(days=2), captured_at=captured)
    return conversions.Attribution(intent=intent, authorization=authorization, accepted=accepted, ticket=ticket, window=window,
        actor_id="manager", reason="Explicit declared attribution, no causal claim", idempotency_key="conversion-link")


@pytest.mark.parametrize("channel", [0, 1, 2])
def test_three_channel_complete_backend_fingerprints_support_explicit_attribution(channel):
    record = source(channel)
    assert record.basis == "explicit_manager_link" and not record.causal_effect_proven and not record.delivery_confirmed
    assert record.intent.submission.account.mode == "test"  # Fixture evidence never becomes live performance.


def test_attribution_rejects_wrong_sources_future_clocks_and_inferred_acceptance():
    record = source(); raw = record.model_dump(mode="json")
    def change(path, value):
        v = json.loads(json.dumps(raw)); cursor = v
        for key in path[:-1]: cursor = cursor[key]
        cursor[path[-1]] = value
        with pytest.raises(ValueError): conversions.Attribution.model_validate(v)
    change(["intent", "request_fingerprint"], "0" * 64)
    change(["intent", "request", "customer_id"], "foreign")
    change(["authorization", "request", "reason"], "Different reason")
    change(["authorization", "revision", "state"], "APPROVE")
    change(["authorization", "revision", "previous_id"], "foreign-approval")
    change(["accepted", "request", "intent_id"], "foreign-intent")
    change(["accepted", "request", "result", "status"], "unknown")
    change(["accepted", "request", "result", "provider_message_id"], None)
    change(["accepted", "request", "result", "delivery_confirmed"], True)
    change(["ticket", "customer_id"], "foreign")
    change(["ticket", "institute_id"], "foreign")
    change(["ticket", "closed_at"], record.window.end.isoformat())
    change(["window", "start"], (record.accepted.request.result.observed_at - timedelta(microseconds=1)).isoformat())
    change(["ticket", "captured_at"], (record.window.captured_at + timedelta(microseconds=1)).isoformat())
    change(["actor_id"], "manager\nsecret")
    change(["causal_effect_proven"], True)
    change(["causal_effect_proven"], 0)
    change(["delivery_confirmed"], "false")
    invalid = record.model_copy(update={"accepted": record.accepted.model_copy(update={"actor_id": " bad "})})
    with pytest.raises(ValueError): conversions.Attribution.model_validate(invalid.model_dump())


def test_preparation_after_send_remains_valid_with_explicit_post_acceptance_billing_window():
    record = source()
    earlier = record.intent.created_at
    authorization = record.authorization.model_copy(update={"revision": record.authorization.revision.model_copy(update={"created_at": earlier})})
    eligibility = record.intent.submission.eligibility.model_copy(update={"captured_at": earlier + timedelta(microseconds=1)})
    submission = record.intent.submission.model_copy(update={"eligibility": eligibility})
    fingerprint = provider.fingerprint(submission)
    intent = record.intent.model_copy(update={"submission": submission, "created_at": eligibility.captured_at, "request_fingerprint": fingerprint})
    observed = earlier + timedelta(microseconds=2)
    result = record.accepted.request.result.model_copy(update={"observed_at": observed, "request_fingerprint": fingerprint})
    accepted = record.accepted.model_copy(update={"created_at": observed, "request": record.accepted.request.model_copy(update={"result": result})})
    valid = conversions.Attribution.model_validate(record.model_copy(update={"authorization": authorization, "intent": intent, "accepted": accepted,
        "window": record.window.model_copy(update={"start": observed})}).model_dump())
    assert valid.intent.created_at > valid.authorization.revision.created_at


def test_summary_exact_money_diagnostics_and_no_test_live_or_currency_mix():
    first = source()
    window = conversions.SummaryWindow(institute_id=first.ticket.institute_id, campaign_id=first.intent.request.campaign_id,
        start=first.window.start, end=first.window.end, captured_at=first.window.captured_at)
    records = []
    for index, (currency, quality, amount) in enumerate([("CHF", "known", "9999999999"), ("CHF", "known", "9999999999"),
        ("EUR", "known", "12345"), ("CHF", "missing", None), ("EUR", "invalid", None), (None, "known", "100")]):
        records.append(conversions.Attribution.model_validate(first.model_copy(update={"idempotency_key": f"link-{index}",
            "ticket": first.ticket.model_copy(update={"ticket_id": f"ticket-{index}", "currency": currency, "amount_quality": quality, "amount_minor": amount})}).model_dump()))
    summary = conversions.summarize(window, records)
    assert summary.linked_tickets == summary.test_linked_tickets == 6 and summary.live_linked_tickets == 0
    assert summary.unknown_currency_test_tickets == 1 and summary.unknown_currency_live_tickets == 0
    assert [(g.mode, g.currency, g.known_gross_minor) for g in summary.currencies] == [("test", "CHF", "19999999998"), ("test", "EUR", "12345")]
    assert summary.currencies[0].missing_amount_tickets == summary.currencies[1].invalid_amount_tickets == 1
    assert summary.conversion_rate is summary.return_on_ad_spend is None
    assert not summary.complete_campaign_history and not summary.causal_effect_proven
    assert conversions.summarize(window, []).linked_tickets == 0
    # Explicit synthetic live-mode terms must never merge with retained test vectors.
    live_account = first.intent.submission.account.model_copy(update={"mode": "live"})
    live_submission = first.intent.submission.model_copy(update={"account": live_account})
    fingerprint = provider.fingerprint(live_submission)
    live_intent = first.intent.model_copy(update={"submission": live_submission, "request_fingerprint": fingerprint})
    live_result = first.accepted.request.result.model_copy(update={"account": live_account, "request_fingerprint": fingerprint})
    live_accepted = first.accepted.model_copy(update={"request": first.accepted.request.model_copy(update={"result": live_result})})
    live = conversions.Attribution.model_validate(first.model_copy(update={"intent": live_intent, "accepted": live_accepted,
        "idempotency_key": "live-link", "ticket": first.ticket.model_copy(update={"ticket_id": "live-ticket"})}).model_dump())
    mixed = conversions.summarize(window, records + [live])
    assert mixed.live_linked_tickets == 1 and mixed.test_linked_tickets == 6
    assert [(g.mode, g.currency, g.known_gross_minor) for g in mixed.currencies] == [("live", "CHF", "12345"), ("test", "CHF", "19999999998"), ("test", "EUR", "12345")]
    for bad in ([records[0], records[0]], [records[0], records[1].model_copy(update={"idempotency_key": records[0].idempotency_key})]):
        with pytest.raises(ValueError): conversions.summarize(window, bad)
    with pytest.raises(ValueError): conversions.summarize(window.model_copy(update={"campaign_id": "foreign"}), records)
    with pytest.raises(ValueError): conversions.summarize(window.model_copy(update={"captured_at": window.end}), records)
