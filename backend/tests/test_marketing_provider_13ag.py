from datetime import timedelta, timezone
import pytest
from app.modules.marketing import contacts, provider
from app.modules.marketing.campaigns import create, transition
from test_marketing_contacts_13w import NOW, sources, declaration

def submission(channel="email", mode="test"):
    customer, _, campaign = sources(channel)
    eligibility = contacts.evaluate(customer, campaign, declaration(), NOW)
    account = provider.Account(institute_id="i", provider="fixture", account_id="account", channel=channel, sender_id="sender", mode=mode,
        push_application="institute-app" if channel == "push" else None)
    return provider.Submission(account=account, eligibility=eligibility, actor_id="manager", idempotency_key="operation")

def result(request, status="accepted"):
    return provider.Result(account=request.account, idempotency_key=request.idempotency_key, request_fingerprint=provider.fingerprint(request),
        status=status, provider_message_id="message" if status == "accepted" else None, observed_at=NOW)

@pytest.mark.parametrize("channel", ["email", "sms", "push"])
def test_channel_submission_pins_approved_owned_sources_and_explicit_account(channel):
    request = submission(channel)
    assert provider.Submission.model_validate_json(request.model_dump_json()) == request
    assert "explicit-device-token" not in repr(request) and "customer@example.com" not in repr(request)
    for status in ("accepted", "rejected", "unknown"):
        checked = provider.validate_result(request, result(request, status))
        assert checked.status == status and not checked.delivery_confirmed
    customer, draft, _ = sources(channel)
    for campaign, original in [(draft, declaration()), (request.eligibility.campaign, None),
            (request.eligibility.campaign, declaration("refused")), (request.eligibility.campaign, declaration("unknown")),
            (request.eligibility.campaign, declaration(destination=False))]:
        denied = contacts.evaluate(customer, campaign, original, NOW)
        with pytest.raises(ValueError): provider.Submission(**{**request.model_dump(), "eligibility": denied})
    for patch in ({"institute_id": "other"}, {"channel": "sms" if channel != "sms" else "email"}, {"push_application": "other"}):
        bad = request.account.model_copy(update=patch)
        with pytest.raises(ValueError): provider.Submission(**{**request.model_dump(), "account": bad})

def test_outcome_cannot_cross_accounts_keys_modes_payloads_or_source_clocks():
    request = submission()
    r = result(request)
    for patch in ({"idempotency_key": "another"}, {"request_fingerprint": "0" * 64}, {"observed_at": NOW - timedelta(microseconds=1)},
            {"account": request.account.model_copy(update={"mode": "live"})}, {"account": request.account.model_copy(update={"account_id": "other"})},
            {"delivery_confirmed": True}, {"delivery_confirmed": 0}, {"provider_message_id": None}):
        with pytest.raises(ValueError): provider.validate_result(request, r.model_copy(update=patch))
    for patch in ({"actor_id": "other"}, {"idempotency_key": "other"}):
        changed = provider.Submission(**{**request.model_dump(), **patch})
        assert provider.fingerprint(changed) != provider.fingerprint(request)
        with pytest.raises(ValueError): provider.validate_result(changed, r)
    bad = request.eligibility.model_copy(update={"eligible_by_current_declaration": True, "reason": "permission_refused"})
    with pytest.raises(ValueError): provider.Submission(**{**request.model_dump(), "eligibility": bad})
    for value in (" operation ", "operation\x00"):
        with pytest.raises(ValueError): provider.Submission(**{**request.model_dump(), "idempotency_key": value})

def test_fingerprint_normalizes_instants_but_preserves_microseconds_and_ordered_terms():
    request = submission()
    payload = request.model_dump()
    payload["eligibility"]["captured_at"] = NOW.astimezone(timezone(timedelta(hours=2)))
    assert provider.fingerprint(provider.Submission(**payload)) == provider.fingerprint(request)
    payload["eligibility"]["captured_at"] += timedelta(microseconds=1)
    assert provider.fingerprint(provider.Submission(**payload)) != provider.fingerprint(request)
    original = request.eligibility.original
    changed = original.model_copy(update={"reason": "Different retained declaration evidence"})
    eligibility = contacts.evaluate(request.eligibility.customer, request.eligibility.campaign, changed, NOW)
    altered = provider.Submission(**{**request.model_dump(), "eligibility": eligibility})
    assert provider.fingerprint(altered) != provider.fingerprint(request)
    with pytest.raises(ValueError): provider.validate_result(altered, result(request))
    content = request.eligibility.campaign.content.model_copy(update={"body": "Changed explicit approved content"})
    draft = create("d2", "campaign", content, "manager", "Changed draft", NOW)
    review = transition(draft, draft.id, "r2", "review", "manager", "Changed review", NOW, None)
    approval = transition(review, review.id, "a2", "approve", "manager", "Changed approval", NOW, None)
    eligibility = contacts.evaluate(request.eligibility.customer, approval, original, NOW)
    altered = provider.Submission(**{**request.model_dump(), "eligibility": eligibility})
    with pytest.raises(ValueError): provider.validate_result(altered, result(request))
    foreign = original.model_copy(update={"declaration": original.declaration.model_copy(update={"customer_id": "foreign"})})
    nested = request.eligibility.model_copy(update={"original": foreign})
    with pytest.raises(ValueError): provider.Submission(**{**request.model_dump(), "eligibility": nested})

def test_fake_adapter_lost_reply_reconciles_same_key_without_a_second_submission():
    class Fake:
        def __init__(self): self.saved = {}; self.calls = 0
        def submit(self, request):
            scope = (request.account.institute_id, request.account.account_id, request.idempotency_key)
            if scope in self.saved:
                prior = self.saved[scope]; provider.validate_result(request, prior); return prior
            self.calls += 1; self.saved[scope] = result(request)
            raise TimeoutError("simulated committed acceptance with lost reply")
        def reconcile(self, request):
            return self.saved.get((request.account.institute_id, request.account.account_id, request.idempotency_key), result(request, "unknown"))
    fake = Fake(); assert isinstance(fake, provider.MarketingProvider)
    request = submission()
    with pytest.raises(TimeoutError): fake.submit(request)
    reconciled = provider.validate_result(request, fake.reconcile(request))
    assert reconciled.status == "accepted" and not reconciled.delivery_confirmed and fake.calls == 1
    assert fake.submit(request) == reconciled and fake.calls == 1
    changed = request.model_copy(update={"actor_id": "another"})
    with pytest.raises(ValueError): fake.submit(changed)
    new = request.model_copy(update={"idempotency_key": "unobserved"})
    assert provider.validate_result(new, fake.reconcile(new)).status == "unknown"
