"""Explicit observed-cohort segmentation; no default commercial thresholds."""
from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, model_validator

from app.modules.crm.metrics import Count, Fact, Identifier, RecordedBilling, Unsigned, microseconds

Positive = Annotated[int, Field(strict=True, gt=0)]
State = Literal["NEW", "ACTIVE", "LOYAL", "VIP", "AT_RISK", "DORMANT"]


class SegmentPolicy(Fact):
    institute_id: Identifier
    observation_us: Positive
    new_customer_us: Positive
    at_risk_us: Positive
    dormant_us: Positive
    loyal_min_tickets: Positive
    vip_min_tickets: Positive
    vip_currency: Literal["CHF", "EUR"]
    vip_gross_minor: Unsigned

    @model_validator(mode="after")
    def ordered(self):
        if not self.at_risk_us < self.dormant_us < self.observation_us:
            raise ValueError("Recency thresholds must be ordered inside the observed horizon")
        if self.new_customer_us > self.observation_us or self.loyal_min_tickets >= self.vip_min_tickets:
            raise ValueError("New age must fit the horizon and VIP count must exceed loyal count")
        return self


class RegisteredCustomerFact(Fact):
    institute_id: Identifier
    customer_id: Identifier
    created_at: AwareDatetime


class ObservedSegment(Fact):
    basis: Literal["declared_policy_observed_billing"] = "declared_policy_observed_billing"
    policy: SegmentPolicy
    customer: RegisteredCustomerFact
    billing: RecordedBilling
    undated_paid_tickets: Count
    state: State | None
    reason: Literal["recent_registration", "recent_activity", "loyal_count", "vip_count_and_gross",
        "risk_recency", "dormant_recency", "stale_window", "undated_closings",
        "no_observed_closing", "uncertain_vip_gross"]
    complete_customer_history: Literal[False] = False


def classify(policy: SegmentPolicy, customer: RegisteredCustomerFact,
             billing: RecordedBilling, undated_paid_tickets: Count) -> ObservedSegment:
    window = billing.window
    if (policy.institute_id != window.institute_id or customer.institute_id != window.institute_id
        or customer.customer_id != window.customer_id or customer.created_at > window.captured_at):
        raise ValueError("Policy, registered customer and observed billing scope must agree")
    if microseconds(window.end-window.start) != policy.observation_us:
        raise ValueError("Billing horizon must match the explicit policy")
    # Validate diagnostics even when an earlier branch returns unknown.
    if type(undated_paid_tickets) is not int or undated_paid_tickets < 0:
        raise ValueError("An explicit nonnegative undated closing count is required")
    state = None
    if window.end != window.captured_at:
        reason = "stale_window"
    elif undated_paid_tickets:
        reason = "undated_closings"
    elif billing.closed_tickets == 0:
        if microseconds(window.captured_at-customer.created_at) <= policy.new_customer_us:
            state, reason = "NEW", "recent_registration"
        else:
            reason = "no_observed_closing"
    else:
        if billing.recorded_recency_us is None:
            raise ValueError("A nonempty observed cohort requires recency")
        recency = int(billing.recorded_recency_us)
        if recency >= policy.dormant_us:
            state, reason = "DORMANT", "dormant_recency"
        elif recency >= policy.at_risk_us:
            state, reason = "AT_RISK", "risk_recency"
        elif billing.closed_tickets >= policy.vip_min_tickets:
            currency = next((g for g in billing.currencies if g.currency == policy.vip_currency), None)
            gross = int(currency.known_gross_minor) if currency else 0
            uncertain = billing.unknown_currency_tickets or currency and (
                currency.missing_amount_tickets or currency.invalid_amount_tickets)
            if gross >= int(policy.vip_gross_minor):
                state, reason = "VIP", "vip_count_and_gross"
            elif uncertain:
                reason = "uncertain_vip_gross"
            else:
                state, reason = "LOYAL", "loyal_count"
        elif billing.closed_tickets >= policy.loyal_min_tickets:
            state, reason = "LOYAL", "loyal_count"
        else:
            state, reason = "ACTIVE", "recent_activity"
    return ObservedSegment(policy=policy, customer=customer, billing=billing,
        undated_paid_tickets=undated_paid_tickets, state=state, reason=reason)
