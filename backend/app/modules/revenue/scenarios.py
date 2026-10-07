"""Exact hypothetical future gross from an explicit historical rate assumption."""
from datetime import datetime
from fractions import Fraction
from typing import Literal
from pydantic import AwareDatetime, field_validator, model_validator
from app.modules.crm.metrics import Fact, Identifier, ExactRatio, microseconds
from app.modules.crm.lifetime import FractionAssumption
from app.modules.revenue.billing import Billing
from app.modules.revenue import sources
from app.shared.exceptions import business_error


class Request(Fact):
    model: Literal["constant_recorded_gross_rate_v1"]
    observed_start: AwareDatetime
    observed_end: AwareDatetime
    projected_start: AwareDatetime
    projected_end: AwareDatetime
    currency: Literal["CHF", "EUR"]
    activity_fraction: FractionAssumption

    @field_validator("observed_start", "observed_end", "projected_start", "projected_end", mode="before")
    @classmethod
    def explicit_time(cls, value):
        if not isinstance(value, (datetime, str)) or isinstance(value, datetime) and value.utcoffset() is None \
                or isinstance(value, str) and "T" not in value:
            raise ValueError("Explicit aware scenario instants are required")
        return value

    @model_validator(mode="after")
    def chronology(self):
        if not self.observed_start < self.observed_end <= self.projected_start < self.projected_end:
            raise ValueError("An observed period followed by a positive future scenario is required")
        return self


class Calculation(Fact):
    institute_id: Identifier
    actor_id: str
    assumptions: Request
    evidence: Billing
    basis: Literal["explicit_constant_historical_rate_scenario"] = "explicit_constant_historical_rate_scenario"
    projected_gross_minor: ExactRatio | None
    confidence: Literal["conditional_unvalidated_scenario"] = "conditional_unvalidated_scenario"
    unavailable_reason: Literal["unknown_currency", "undated_paid_tickets", "no_selected_currency", "uncertain_amounts"] | None
    validated_prediction: Literal[False] = False
    action_executed: Literal[False] = False

    @field_validator("validated_prediction", "action_executed", mode="before")
    @classmethod
    def no_claim(cls, value):
        if value is not False:
            raise ValueError("A scenario preview cannot certify a forecast or execute an action")
        return value


class Scenario(Calculation):
    retained: Literal[False] = False

    @field_validator("retained", mode="before")
    @classmethod
    def preview_only(cls, value):
        if value is not False:
            raise ValueError("A preview is not a retained original")
        return value


def calculate(institute, actor, request: Request, billing: Billing):
    request = Request.model_validate(request.model_dump())
    billing = Billing.model_validate(billing.model_dump())
    if not isinstance(actor, str) or not actor or actor != actor.strip() or len(actor) > 160 or any(ord(c) < 32 for c in actor):
        raise ValueError("An explicit signed scenario actor is required")
    window = billing.window
    if window.institute_id != institute or window.start != request.observed_start or window.end != request.observed_end \
            or request.projected_start < window.captured_at:
        raise ValueError("Scenario scope and observed capture must match its retained input terms")
    groups = [group for group in billing.ticket_amounts if group.currency == request.currency]
    unknown = any(group.currency is None and group.source_count for group in billing.ticket_amounts)
    reason = "unknown_currency" if unknown else "undated_paid_tickets" if billing.institute_undated_paid_tickets \
        else "no_selected_currency" if not groups else "uncertain_amounts" if groups[0].complete_gross_minor is None else None
    if len(groups) > 1:
        raise ValueError("A unique selected currency evidence group is required")
    amount = None
    if reason is None:
        value = Fraction(int(groups[0].complete_gross_minor), microseconds(window.end-window.start)) \
            * microseconds(request.projected_end-request.projected_start) \
            * Fraction(int(request.activity_fraction.numerator), int(request.activity_fraction.denominator))
        amount = ExactRatio(numerator=str(value.numerator), denominator=str(value.denominator))
    return Scenario(institute_id=institute, actor_id=actor, assumptions=request, evidence=billing,
        projected_gross_minor=amount, unavailable_reason=reason)


def preview(db, institute, request: Request, actor):
    # Source service pins its own clock under the shared lock. Public payloads
    # carry assumptions only, never billing amounts or a caller capture clock.
    try:
        request = Request.model_validate(request.model_dump())
        billing = sources.read(db, institute, request.observed_start, request.observed_end)
        return calculate(institute, actor, request, billing)
    except ValueError as error:
        raise business_error("Scenario terms or recorded sources require verification") from error
