"""Explicit source-backed billing attribution; no inferred causal conversion or I/O."""
from typing import Iterable, Literal
from pydantic import AwareDatetime, model_validator, field_validator
from app.modules.crm.metrics import Fact, Identifier, Count, Unsigned, BillingWindow, ClosedTicketFact
from app.modules.crm.policies import Reason, Key
from app.modules.marketing import campaign_originals, dispatch_intents, dispatch_outcomes, provider


class NoClaims(Fact):
    @field_validator("causal_effect_proven", "delivery_confirmed", "complete_campaign_history", mode="before", check_fields=False)
    @classmethod
    def strict_false(cls, value):
        if value is not False:
            raise ValueError("Attribution cannot assert causality, delivery or complete history")
        return value


class Attribution(NoClaims):
    intent: dispatch_intents.Original
    authorization: campaign_originals.Original
    accepted: dispatch_outcomes.Original
    ticket: ClosedTicketFact
    window: BillingWindow
    actor_id: provider.Exact
    reason: Reason
    idempotency_key: Key
    basis: Literal["explicit_manager_link"] = "explicit_manager_link"
    causal_effect_proven: Literal[False] = False
    delivery_confirmed: Literal[False] = False

    @model_validator(mode="after")
    def source_links(self):
        # Revalidate typed model_copy/model_construct inputs at this boundary.
        intent = dispatch_intents.Original.model_validate(self.intent.model_dump())
        submission = provider.Submission.model_validate(intent.submission.model_dump())
        r, e = intent.request, submission.eligibility
        if (r.campaign_id, r.expected_revision_id, r.customer_id, r.expected_contact_id, r.account_id, r.idempotency_key) != (
            e.campaign.campaign_id, e.campaign.id, e.customer.customer_id, e.original.id,
            submission.account.account_id, submission.idempotency_key):
            raise ValueError("Attribution intent terms differ from complete submission")
        if intent.created_at != e.captured_at or intent.request_fingerprint != provider.fingerprint(submission):
            raise ValueError("Attribution intent capture/fingerprint differs")
        authorization = campaign_originals.Original.model_validate(self.authorization.model_dump())
        send = authorization.revision
        if (send.institute_id, send.campaign_id, send.state, send.previous_id) != (
            submission.account.institute_id, r.campaign_id, "SEND", e.campaign.id):
            raise ValueError("Attribution requires the exact owned SEND successor")
        if send.content != e.campaign.content or send.reviewed_digest != e.campaign.reviewed_digest or send.approved_digest != e.campaign.approved_digest:
            raise ValueError("Attribution SEND must retain unchanged approved content")
        if authorization.request.action != "send" or authorization.request.campaign_id != r.campaign_id or authorization.request.expected_revision_id != e.campaign.id or authorization.request.content is not None:
            raise ValueError("Attribution authorization request differs from SEND")
        if send.reason != authorization.request.reason or send.id == e.campaign.id or send.created_at < e.campaign.created_at:
            raise ValueError("Attribution authorization original differs from its request/predecessor")
        accepted = dispatch_outcomes.Original.model_validate(self.accepted.model_dump())
        result = provider.validate_result(submission, accepted.request.result)
        if accepted.request.intent_id != intent.id or accepted.request.expected_previous_id == accepted.id or result.status != "accepted":
            raise ValueError("Attribution requires an accepted observation bound to this intent")
        if max(intent.created_at, send.created_at) > result.observed_at or result.observed_at > accepted.created_at:
            raise ValueError("Attribution source clocks are incoherent")
        ticket = ClosedTicketFact.model_validate(self.ticket.model_dump())
        window = BillingWindow.model_validate(self.window.model_dump())
        if (ticket.institute_id, ticket.customer_id, window.institute_id, window.customer_id) != (
            submission.account.institute_id, r.customer_id, submission.account.institute_id, r.customer_id):
            raise ValueError("Attribution billing sources belong to another recipient")
        if ticket.captured_at != window.captured_at or accepted.created_at > window.captured_at:
            raise ValueError("Attribution requires one nonfuture billing capture")
        if not result.observed_at <= window.start <= ticket.closed_at < window.end:
            raise ValueError("Attributed ticket must be inside an explicit post-acceptance window")
        if any(v != v.strip() or any(ord(c) < 32 or ord(c) == 127 for c in v) for v in (self.actor_id, accepted.actor_id, send.actor_id)):
            raise ValueError("Exact non-control attribution/source actors required")
        return self


class SummaryWindow(Fact):
    institute_id: Identifier
    campaign_id: Identifier
    start: AwareDatetime
    end: AwareDatetime
    captured_at: AwareDatetime

    @model_validator(mode="after")
    def chronology(self):
        if not self.start < self.end <= self.captured_at:
            raise ValueError("Explicit observed attribution summary window required")
        return self


class CurrencyAttribution(Fact):
    mode: Literal["test", "live"]
    currency: Literal["CHF", "EUR"]
    linked_tickets: Count
    known_amount_tickets: Count
    missing_amount_tickets: Count
    invalid_amount_tickets: Count
    known_gross_minor: Unsigned


class Summary(NoClaims):
    window: SummaryWindow
    basis: Literal["explicit_manager_links"] = "explicit_manager_links"
    linked_tickets: Count
    live_linked_tickets: Count
    test_linked_tickets: Count
    unknown_currency_live_tickets: Count
    unknown_currency_test_tickets: Count
    currencies: tuple[CurrencyAttribution, ...]
    complete_campaign_history: Literal[False] = False
    causal_effect_proven: Literal[False] = False
    delivery_confirmed: Literal[False] = False
    conversion_rate: None = None
    return_on_ad_spend: None = None


def summarize(window: SummaryWindow, sources: Iterable[Attribution]) -> Summary:
    window = SummaryWindow.model_validate(window.model_dump())
    tickets, keys, groups = set(), set(), {}
    modes = {"live": 0, "test": 0}; unknown = {"live": 0, "test": 0}
    for source in sources:
        source = Attribution.model_validate(source.model_dump())
        ticket = source.ticket; account = source.intent.submission.account
        if account.institute_id != window.institute_id or source.intent.request.campaign_id != window.campaign_id:
            raise ValueError("Attribution summary campaign scope differs")
        if source.window.captured_at > window.captured_at or not window.start <= ticket.closed_at < window.end:
            raise ValueError("Attribution source is outside the observed summary")
        if ticket.ticket_id in tickets or source.idempotency_key in keys:
            raise ValueError("An attributed ticket or operation key cannot be counted twice")
        tickets.add(ticket.ticket_id); keys.add(source.idempotency_key); modes[account.mode] += 1
        if ticket.currency is None:
            unknown[account.mode] += 1; continue
        group = groups.setdefault((account.mode, ticket.currency), {"linked_tickets": 0, "known_amount_tickets": 0,
            "missing_amount_tickets": 0, "invalid_amount_tickets": 0, "gross": 0})
        group["linked_tickets"] += 1; group[ticket.amount_quality + "_amount_tickets"] += 1
        if ticket.amount_minor is not None: group["gross"] += int(ticket.amount_minor)
    currencies = tuple(CurrencyAttribution(mode=mode, currency=currency,
        known_gross_minor=str(group["gross"]), **{key: value for key, value in group.items() if key != "gross"})
        for (mode, currency), group in sorted(groups.items()))
    return Summary(window=window, linked_tickets=len(tickets), live_linked_tickets=modes["live"], test_linked_tickets=modes["test"],
        unknown_currency_live_tickets=unknown["live"], unknown_currency_test_tickets=unknown["test"], currencies=currencies)
