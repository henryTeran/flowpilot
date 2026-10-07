"""Explicit finite remaining-lifetime scenario, not a learned or certified forecast."""
from datetime import timedelta, timezone
from fractions import Fraction
from typing import Annotated, Literal

from pydantic import AwareDatetime, StringConstraints, model_validator

from app.modules.crm.metrics import Count, Fact, Identifier, RecordedBilling, microseconds

Unsigned = Annotated[str, StringConstraints(pattern=r"^(0|[1-9][0-9]*)$", max_length=30)]
Positive = Annotated[str, StringConstraints(pattern=r"^[1-9][0-9]*$", max_length=30)]


class FractionAssumption(Fact):
    numerator: Unsigned
    denominator: Positive

    @model_validator(mode="after")
    def bounded(self):
        if int(self.numerator) > int(self.denominator):
            raise ValueError("An explicitly declared fraction between zero and one is required")
        return self


class LifetimeAssumptions(Fact):
    institute_id: Identifier
    customer_id: Identifier
    model: Literal["constant_observed_rate_finite_remaining_lifetime_undiscounted_v1"]
    currency: Literal["CHF", "EUR"]
    expected_active_us: Positive
    activity_fraction: FractionAssumption
    gross_contribution_margin: FractionAssumption
    future_relationship_cost_minor: Unsigned


class SignedRatio(Fact):
    numerator: Annotated[str, StringConstraints(pattern=r"^(0|-?[1-9][0-9]*)$")]
    denominator: Annotated[str, StringConstraints(pattern=r"^[1-9][0-9]*$")]


class RemainingLifetimeScenario(Fact):
    basis: Literal["declared_remaining_lifetime_scenario"] = "declared_remaining_lifetime_scenario"
    assumptions: LifetimeAssumptions
    billing: RecordedBilling
    undated_paid_tickets: Count
    future_paid_tickets: Count
    assumed_active_until: AwareDatetime | None
    projected_gross_minor: SignedRatio | None
    projected_contribution_minor: SignedRatio | None
    remaining_clv_minor: SignedRatio | None
    unavailable_reason: Literal["stale_window", "undated_closings", "future_closings", "unrepresentable_lifetime",
        "unknown_currency", "no_observed_currency", "uncertain_amounts"] | None
    complete_customer_history: Literal[False] = False
    validated_prediction: Literal[False] = False
    discounted: Literal[False] = False


def ratio(value: Fraction) -> SignedRatio:
    return SignedRatio(numerator=str(value.numerator), denominator=str(value.denominator))


def calculate_remaining_lifetime(assumptions: LifetimeAssumptions, billing: RecordedBilling,
                                 undated_paid_tickets: int, future_paid_tickets: int) -> RemainingLifetimeScenario:
    """A source-backed rate and explicitly declared assumptions produce a scenario only.

    Gross = selected-currency observed gross / observed duration * assumed active
    duration * activity fraction. Contribution applies the declared gross margin;
    remaining CLV subtracts declared future relationship costs in that currency.
    No FX, discounting, automatic lifetime/retention/margin, or historical net value.
    """
    window = billing.window
    if (assumptions.institute_id != window.institute_id or assumptions.customer_id != window.customer_id):
        raise ValueError("Lifetime assumptions and billing customer/institute must agree")
    for count in (undated_paid_tickets, future_paid_tickets):
        if type(count) is not int or count < 0:
            raise ValueError("Explicit nonnegative closing diagnostics are required")
    reason = None; until = None; gross = contribution = net = None
    if window.end != window.captured_at:
        reason = "stale_window"
    elif undated_paid_tickets:
        reason = "undated_closings"
    elif future_paid_tickets:
        reason = "future_closings"
    else:
        try:
            until = window.captured_at.astimezone(timezone.utc) + timedelta(microseconds=int(assumptions.expected_active_us))
        except OverflowError:
            reason = "unrepresentable_lifetime"
        if reason is None:
            selected = next((g for g in billing.currencies if g.currency == assumptions.currency), None)
            if billing.unknown_currency_tickets:
                reason = "unknown_currency"
            elif selected is None:
                reason = "no_observed_currency"
            elif selected.missing_amount_tickets or selected.invalid_amount_tickets:
                reason = "uncertain_amounts"
            else:
                activity = assumptions.activity_fraction; margin = assumptions.gross_contribution_margin
                duration = microseconds(window.end.astimezone(timezone.utc)-window.start.astimezone(timezone.utc))
                gross = Fraction(int(selected.known_gross_minor)*int(assumptions.expected_active_us), duration)
                gross *= Fraction(int(activity.numerator), int(activity.denominator))
                contribution = gross*Fraction(int(margin.numerator), int(margin.denominator))
                net = contribution-int(assumptions.future_relationship_cost_minor)
    return RemainingLifetimeScenario(assumptions=assumptions, billing=billing,
        undated_paid_tickets=undated_paid_tickets, future_paid_tickets=future_paid_tickets,
        assumed_active_until=until, projected_gross_minor=ratio(gross) if gross is not None else None,
        projected_contribution_minor=ratio(contribution) if contribution is not None else None,
        remaining_clv_minor=ratio(net) if net is not None else None, unavailable_reason=reason)
