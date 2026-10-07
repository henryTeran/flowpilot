from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.modules.crm.segments import RegisteredCustomerFact
from app.modules.marketing import contacts
from app.modules.marketing.campaigns import AudienceFact, CampaignContent, create, transition

NOW = datetime(2026, 10, 7, 12, tzinfo=timezone.utc)


def declaration(permission="granted", destination=True):
    values = []
    for channel in ("email", "sms", "push"):
        endpoint = contacts.Destination(channel=channel, email="customer@example.com" if channel == "email" else None,
            phone="+41791234567" if channel == "sms" else None, push_application="institute-app" if channel == "push" else None,
            push_token="explicit-device-token" if channel == "push" else None, evidence="Explicit destination declaration") if destination else None
        values.append(contacts.Communication(channel=channel, permission=permission,
            permission_evidence="Explicit channel permission" if permission != "unknown" else None, destination=endpoint))
    return contacts.Original(id="o", previous_id=None, actor_id="manager", created_at=NOW, reason="Explicit full-channel declaration", idempotency_key="contact-key",
        declaration=contacts.Declaration(institute_id="i", customer_id="c", communications=tuple(values)))


def sources(channel="email"):
    customer = RegisteredCustomerFact(institute_id="i", customer_id="c", created_at=NOW)
    content = CampaignContent(institute_id="i", channel=channel, origin="ai", subject="Explicit email" if channel == "email" else None,
        body="Literal {customer_name}", template_original_id=None, audience=AudienceFact(id="aud", institute_id="i", captured_at=NOW, customer_ids=("c",)))
    draft = create("d", "campaign", content, "manager", "Explicit draft", NOW)
    review = transition(draft, "d", "r", "review", "manager", "Explicit review", NOW, None)
    approved = transition(review, "r", "a", "approve", "manager", "Explicit approval", NOW, None)
    return customer, draft, approved


@pytest.mark.parametrize("channel", ["email", "sms", "push"])
def test_each_channel_requires_current_permission_endpoint_and_approval(channel):
    customer, draft, approved = sources(channel)
    original = declaration()
    result = contacts.evaluate(customer, approved, original, NOW)
    assert result.reason == "declared_eligible" and result.eligible_by_current_declaration
    assert not result.delivery_authorized and not result.external_message_sent
    assert contacts.Eligibility.model_validate_json(result.model_dump_json()) == result
    for retained, expected in [(None, "declaration_absent"), (declaration("unknown"), "permission_unknown"),
            (declaration("refused"), "permission_refused"), (declaration(destination=False), "destination_absent")]:
        denied = contacts.evaluate(customer, approved, retained, NOW)
        assert denied.reason == expected and not denied.eligible_by_current_declaration
    assert contacts.evaluate(customer, draft, original, NOW).reason == "campaign_not_approved"
    # A later withdrawal defeats historical eligibility, without editing campaign approval.
    withdrawn = declaration("refused").model_copy(update={"id": "withdrawn", "previous_id": original.id, "created_at": NOW + timedelta(microseconds=1)})
    assert contacts.evaluate(customer, approved, withdrawn, withdrawn.created_at).reason == "permission_refused"
    assert approved.approved_digest is not None


def test_declaration_append_pins_exact_owned_predecessor_without_mutating_it():
    customer, _, _ = sources()
    initial = declaration()
    request = contacts.Request(declaration=initial.declaration, previous_id=None, reason=initial.reason, idempotency_key=initial.idempotency_key)
    assert contacts.record("o", "manager", customer, request, None, NOW) == initial
    before = initial.model_dump_json()
    correction = contacts.Request(declaration=declaration("refused").declaration, previous_id=initial.id, reason="Explicit withdrawal", idempotency_key="withdraw-key")
    changed = contacts.record("new", "signed-manager", customer, correction, initial, NOW + timedelta(microseconds=1))
    assert changed.previous_id == initial.id and changed.actor_id == "signed-manager"
    assert all(c.permission == "refused" for c in changed.declaration.communications)
    assert initial.model_dump_json() == before
    for bad_request, previous, clock, identifier in [
        (correction, None, NOW, "new"), (request, initial, NOW, "new"),
        (correction.model_copy(update={"previous_id": "stale"}), initial, NOW, "new"),
        (correction, initial, NOW - timedelta(microseconds=1), "new"), (correction, initial, NOW, "o")]:
        with pytest.raises(ValueError): contacts.record(identifier, "manager", customer, bad_request, previous, clock)
    for bad in [customer.model_copy(update={"customer_id": "foreign"}), customer.model_copy(update={"institute_id": "foreign"}),
                customer.model_copy(update={"created_at": NOW + timedelta(microseconds=1)})]:
        with pytest.raises(ValueError): contacts.record("new", "manager", bad, request, None, NOW)
    with pytest.raises(ValueError): contacts.record("new", "manager", customer, correction,
        initial.model_copy(update={"declaration": initial.declaration.model_copy(update={"customer_id": "foreign"})}), NOW)


def test_channel_purpose_completeness_and_endpoint_binding_are_explicit():
    original = declaration()
    for communications in [original.declaration.communications[:2], original.declaration.communications + (original.declaration.communications[0],),
                           (original.declaration.communications[0],) * 3]:
        with pytest.raises(ValidationError): contacts.Declaration(institute_id="i", customer_id="c", communications=communications)
    with pytest.raises(ValidationError): contacts.Declaration(**{**original.declaration.model_dump(), "purpose": "service_follow_up"})
    sms = original.declaration.communications[1].destination.model_dump()
    for changes in [{"phone": "0791234567"}, {"phone": "+0123456"}, {"phone": "+41791234567\n"}, {"email": "customer@example.com"}]:
        with pytest.raises(ValidationError): contacts.Destination(**{**sms, **changes})
    push = original.declaration.communications[2].destination.model_dump()
    for changes in [{"push_application": None}, {"push_application": " app "}, {"push_token": "\n"}, {"push_token": "a\x00b"}]:
        with pytest.raises(ValidationError): contacts.Destination(**{**push, **changes})
    email = original.declaration.communications[0].destination.model_dump()
    with pytest.raises(ValidationError): contacts.Destination(**{**email, "email": "not-an-address"})
    with pytest.raises(ValidationError): contacts.Communication(channel="sms", permission="granted", permission_evidence=None, destination=None)
    with pytest.raises(ValidationError): contacts.Communication(channel="email", permission="unknown", permission_evidence="Invented unknown", destination=None)
    with pytest.raises(ValidationError): contacts.Communication(channel="email", permission="granted", permission_evidence="Explicit grant",
        destination=original.declaration.communications[1].destination)
    assert "explicit-device-token" not in repr(original) and "customer@example.com" not in repr(original) and "+41791234567" not in repr(original)


def test_owned_sources_clocks_membership_and_forged_results_refused():
    customer, _, approved = sources()
    original = declaration()
    future = original.model_copy(update={"created_at": NOW + timedelta(microseconds=1)})
    assert contacts.evaluate(customer, approved, future, NOW).reason == "future_declaration"
    assert contacts.evaluate(customer.model_copy(update={"created_at": NOW + timedelta(microseconds=1)}), approved, original, NOW).reason == "future_registration"
    assert contacts.evaluate(customer, approved, original, NOW - timedelta(microseconds=1)).reason == "future_campaign"
    assert contacts.evaluate(customer.model_copy(update={"customer_id": "other"}), approved, None, NOW).reason == "customer_not_retained"
    for changed in [customer.model_copy(update={"institute_id": "foreign"}), customer.model_copy(update={"customer_id": "other"})]:
        with pytest.raises(ValidationError): contacts.evaluate(changed, approved, original, NOW)
    for clock in [NOW.replace(tzinfo=None), "2026-10-07", 1791374400, True]:
        with pytest.raises(ValidationError): contacts.evaluate(customer, approved, original, clock)
    # model_copy does not bypass validation at the domain boundary.
    broken = original.model_copy(update={"declaration": original.declaration.model_copy(update={"communications": ()})})
    with pytest.raises(ValidationError): contacts.evaluate(customer, approved, broken, NOW)
    broken_campaign = approved.model_copy(update={"content": approved.content.model_copy(update={"body": "Forged"})})
    with pytest.raises(ValidationError): contacts.evaluate(customer, broken_campaign, original, NOW)
    result = contacts.evaluate(customer, approved, declaration("refused"), NOW).model_dump()
    for changes in [{"reason": "declared_eligible", "eligible_by_current_declaration": True}, {"eligible_by_current_declaration": 1},
                    {"delivery_authorized": True}, {"external_message_sent": True}]:
        with pytest.raises(ValidationError): contacts.Eligibility.model_validate({**result, **changes})

@pytest.mark.parametrize("channel", ["email", "sms", "push"])
def test_send_preserves_approval_but_never_overrides_current_withdrawal(channel):
    customer, _, approved = sources(channel)
    sent = transition(approved, approved.id, "s", "send", "manager", "Explicit SEND", NOW, None)
    result = contacts.evaluate(customer, sent, declaration(), NOW)
    assert result.eligible_by_current_declaration and result.reason == "declared_eligible"
    assert not result.delivery_authorized and not result.external_message_sent
    assert contacts.evaluate(customer, sent, declaration("refused"), NOW).reason == "permission_refused"
    future = sent.model_copy(update={"created_at":NOW + timedelta(microseconds=1)})
    assert contacts.evaluate(customer, future, declaration(), NOW).reason == "future_campaign"
