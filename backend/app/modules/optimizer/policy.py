"""Explicit normalization terms; no automatic weights or mutable SQL capture."""
from typing import Annotated, Literal
from fractions import Fraction
from datetime import datetime, timezone
from pydantic import AwareDatetime, Field, model_validator
from app.modules.optimizer import domain
Basis = Literal["disabled", "catalog_reference", "proposed_duration_over_free_window",
    "recorded_continuity_indicator", "declared_client_preference_indicator",
    "declared_employee_preference_indicator", "elapsed_start_delay",
    "beyond_declared_working_window", "captured_conflict_indicator"]
BASES = dict(revenue_score="catalog_reference", utilization_score="proposed_duration_over_free_window",
    continuity_score="recorded_continuity_indicator", client_preference_score="declared_client_preference_indicator",
    employee_preference_score="declared_employee_preference_indicator", idle_gap_penalty="elapsed_start_delay",
    overtime_penalty="beyond_declared_working_window", resource_conflict_penalty="captured_conflict_indicator")


class Rule(domain.matching.Fact):
    factor: domain.Factor
    weight: domain.Ratio
    basis: Basis
    ceiling: domain.Positive | None
    currency: Literal["CHF", "EUR"] | None
    price_mode: Literal["member", "passage"] | None
    reason: domain.Text

    @model_validator(mode="after")
    def explicit_terms(self):
        if self.weight.fraction() == 0:
            if self.basis != "disabled" or any(v is not None for v in (self.ceiling, self.currency, self.price_mode)):
                raise ValueError("Disabled factor requires explicit disabled basis without invented normalization")
        elif self.basis != BASES[self.factor]:
            raise ValueError("Enabled factor requires its explicit supported basis")
        if self.basis == "catalog_reference":
            if self.ceiling is None or self.currency is None or self.price_mode is None:
                raise ValueError("Reference revenue requires currency, price mode and minor-unit ceiling")
        elif self.currency is not None or self.price_mode is not None:
            raise ValueError("Only conditional catalog reference has monetary terms")
        if self.basis in {"elapsed_start_delay", "beyond_declared_working_window"}:
            if self.ceiling is None:
                raise ValueError("Elapsed penalties require explicit microsecond ceiling")
        elif self.basis != "catalog_reference" and self.ceiling is not None:
            raise ValueError("Ratio/indicator/disabled basis cannot carry a ceiling")
        return self


class Terms(domain.matching.Fact):
    rules: tuple[Rule, ...] = Field(min_length=8, max_length=8)
    normalization: Literal["exact_unit_interval_explicit_ceiling_saturation"] = "exact_unit_interval_explicit_ceiling_saturation"

    @model_validator(mode="after")
    def complete(self):
        if {r.factor for r in self.rules} != set(domain.FACTORS) or not any(r.weight.fraction() for r in self.rules):
            raise ValueError("Eight unique explicit factors and at least one enabled weight required")
        return self


class Source(domain.matching.Fact):
    factor: domain.Factor
    basis: Basis
    quantity: domain.Unsigned | None
    denominator: domain.Positive | None
    currency: Literal["CHF", "EUR"] | None
    price_mode: Literal["member", "passage"] | None
    reference: domain.Identifier | None
    observed_at: AwareDatetime | None
    reason: domain.Text

    @model_validator(mode="after")
    def coherent(self):
        if self.basis != BASES[self.factor]:
            raise ValueError("Source truth must bind the factor's actual supported basis")
        if self.quantity is None:
            if any(v is not None for v in (self.denominator, self.currency, self.price_mode, self.reference, self.observed_at)):
                raise ValueError("Unavailable source cannot fabricate numeric terms or dated evidence")
        elif self.reference is None or self.observed_at is None:
            raise ValueError("Known source requires dated reference")
        elif self.basis == "catalog_reference":
            if self.currency is None or self.price_mode is None or self.denominator is not None:
                raise ValueError("Catalog reference requires its actual currency and price mode")
        elif self.currency is not None or self.price_mode is not None:
            raise ValueError("Nonmonetary source cannot acquire a currency")
        if self.quantity is not None:
            if self.basis == "proposed_duration_over_free_window":
                if self.denominator is None or int(self.quantity) > int(self.denominator):
                    raise ValueError("Proposed elapsed duration requires a complete containing window")
            elif self.denominator is not None:
                raise ValueError("Only utilization source has a source denominator")
            if self.basis.endswith("_indicator") and self.quantity not in {"0", "1"}:
                raise ValueError("Indicators require an explicit exact binary source")
        return self


class Normalized(domain.matching.Fact):
    rule: Rule
    source: Source
    observation: domain.Observation
    saturated: Literal["yes", "no", "not_computed"]
    meaning: Literal["explicit_policy_normalization_not_quote_profit_or_prediction"] = "explicit_policy_normalization_not_quote_profit_or_prediction"


def normalize(rule: Rule, source: Source, captured_at):
    rule = Rule.model_validate(rule.model_dump())
    source = Source.model_validate(source.model_dump())
    if not isinstance(captured_at, datetime) or captured_at.utcoffset() is None:
        raise ValueError("Aware server capture required")
    captured_at = captured_at.astimezone(timezone.utc)
    if rule.factor != source.factor or source.observed_at is not None and source.observed_at > captured_at:
        raise ValueError("Source must bind factor and captured chronology")
    unknown = dict(factor=rule.factor, state="unknown", value=None, reference=None, observed_at=None, reason=source.reason)
    # Hard current conflicts remain evidence even if the scoring weight is disabled.
    conflict = rule.factor == "resource_conflict_penalty" and source.basis == "captured_conflict_indicator"
    if source.quantity is None or rule.basis == "disabled" and not conflict:
        return Normalized(rule=rule, source=source, observation=domain.Observation(**unknown), saturated="not_computed")
    if not conflict and (rule.basis != source.basis or rule.basis == "catalog_reference"
            and (rule.currency, rule.price_mode) != (source.currency, source.price_mode)):
        raise ValueError("Source normalization basis/currency/mode must exactly match explicit policy")
    value = Fraction(int(source.quantity), int(source.denominator)) if source.basis == "proposed_duration_over_free_window" \
        else Fraction(int(source.quantity), int(rule.ceiling)) if source.basis in {"catalog_reference", "elapsed_start_delay", "beyond_declared_working_window"} \
        else Fraction(int(source.quantity))
    saturated = value > 1
    value = min(value, Fraction(1))
    return Normalized(rule=rule, source=source, observation=domain.Observation(factor=rule.factor, state="known",
        value=domain.Ratio(numerator=str(value.numerator), denominator=str(value.denominator)),
        reference=source.reference, observed_at=source.observed_at, reason=source.reason), saturated="yes" if saturated else "no")


def scoring_policy(terms: Terms, institute, identifier, captured_at, reason):
    terms = Terms.model_validate(terms.model_dump())
    return domain.Policy(institute_id=institute, id=identifier, captured_at=captured_at, reason=reason,
        weights=tuple(domain.Weight(factor=f, value=next(r.weight for r in terms.rules if r.factor == f)) for f in domain.FACTORS))
