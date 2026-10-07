"""Explicit retained variants; never a sum of mutually alternative projections."""
from fractions import Fraction
from typing import Annotated, Literal
from pydantic import AwareDatetime, Field, StringConstraints, field_validator, model_validator
from sqlalchemy import select
from app.modules.crm.metrics import Fact, Identifier, Count
from app.modules.revenue import scenario_originals as originals
from app.modules.revenue.models import ScenarioOriginal
from app.modules.tickets.repository import lock_institute
from app.shared.exceptions import business_error, not_found
from app.shared.time import utcnow


class Reference(Fact):
    original_id: Identifier
    fingerprint: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]

    @field_validator("original_id")
    @classmethod
    def exact_id(cls, value):
        if value != value.strip():
            raise ValueError("An exact retained original ID is required")
        return value


class Request(Fact):
    baseline: Reference
    alternatives: Annotated[tuple[Reference, ...], Field(min_length=1, max_length=19)]

    @model_validator(mode="after")
    def distinct(self):
        identifiers = [self.baseline.original_id, *(r.original_id for r in self.alternatives)]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("Select each retained scenario once")
        return self


class SignedRatio(Fact):
    numerator: Annotated[str, StringConstraints(pattern=r"^(0|-?[1-9][0-9]*)$")]
    denominator: Annotated[str, StringConstraints(pattern=r"^[1-9][0-9]*$")]


class Variant(Fact):
    original: originals.Envelope
    is_baseline: bool = Field(strict=True)
    same_source_capture: bool = Field(strict=True)
    same_recorded_billing_aggregates: bool = Field(strict=True)
    difference_from_baseline_minor: SignedRatio | None
    difference_unavailable_reason: Literal["currency_difference", "model_difference", "observed_period_difference", "projected_period_difference", "unavailable_projection"] | None
    difference_basis: Literal["comparison_only_not_attributed_effect"] = "comparison_only_not_attributed_effect"


class CurrencyGroup(Fact):
    currency: Literal["CHF", "EUR"]
    selected_count: Count
    valued_count: Count
    unavailable_count: Count
    summed_projected_gross_minor: None = None


class Comparison(Fact):
    institute_id: Identifier
    captured_at: AwareDatetime
    baseline_original_id: Identifier
    selected_count: Count
    variants: tuple[Variant, ...]
    currencies: tuple[CurrencyGroup, ...]
    basis: Literal["explicit_retained_scenario_comparison"] = "explicit_retained_scenario_comparison"
    confidence: Literal["conditional_unvalidated_scenarios"] = "conditional_unvalidated_scenarios"
    summed_projected_gross_minor: None = None
    validated_prediction: Literal[False] = False
    causal_effect_confirmed: Literal[False] = False
    action_executed: Literal[False] = False
    full_institute_scenario_cohort: Literal[False] = False

    @field_validator("validated_prediction", "causal_effect_confirmed", "action_executed", "full_institute_scenario_cohort", mode="before")
    @classmethod
    def strict_no_claim(cls, value):
        if value is not False:
            raise ValueError("Selected conditional variants cannot establish totals, causal effects or predictions")
        return value


def _aggregate_terms(original):
    # Capture clocks differ between independent originals. Compare only the
    # returned aggregate terms, never assert identical underlying SQL source IDs.
    value = original.evidence.model_dump(mode="json", exclude={"window"})
    value["window"] = dict(institute_id=original.evidence.window.institute_id,
        start=original.evidence.window.start, end=original.evidence.window.end)
    return value


def _variant(envelope, baseline, is_baseline):
    value = originals.Original.model_validate(envelope.original)
    a, b = value.assumptions, baseline.assumptions
    reason = "currency_difference" if a.currency != b.currency else "model_difference" if a.model != b.model \
        else "observed_period_difference" if (a.observed_start, a.observed_end) != (b.observed_start, b.observed_end) \
        else "projected_period_difference" if (a.projected_start, a.projected_end) != (b.projected_start, b.projected_end) \
        else "unavailable_projection" if value.projected_gross_minor is None or baseline.projected_gross_minor is None else None
    difference = None
    if reason is None:
        def exact(ratio):
            return Fraction(int(ratio.numerator), int(ratio.denominator))
        delta = exact(value.projected_gross_minor) - exact(baseline.projected_gross_minor)
        difference = SignedRatio(numerator=str(delta.numerator), denominator=str(delta.denominator))
    return Variant(original=envelope, is_baseline=is_baseline,
        same_source_capture=value.evidence.window.captured_at == baseline.evidence.window.captured_at,
        same_recorded_billing_aggregates=_aggregate_terms(value) == _aggregate_terms(baseline),
        difference_from_baseline_minor=difference, difference_unavailable_reason=reason)


def read(db, institute, request: Request):
    try:
        request = Request.model_validate(request.model_dump())
    except ValueError as error:
        raise business_error("Explicit distinct retained scenario selections are required") from error
    lock_institute(db, institute)
    now = utcnow()
    selected = [request.baseline, *request.alternatives]
    rows = {row.id: row for row in db.scalars(select(ScenarioOriginal).where(ScenarioOriginal.institute_id == institute,
        ScenarioOriginal.id.in_([r.original_id for r in selected])).execution_options(populate_existing=True))}
    if len(rows) != len(selected):
        raise not_found("Selected retained scenario original not found in this institute")
    verified = []
    for reference in selected:
        envelope = originals.verify(rows[reference.original_id], institute, now)
        if envelope.fingerprint != reference.fingerprint:
            raise business_error("The selected scenario fingerprint changed; review its original")
        verified.append(envelope)
    baseline = originals.Original.model_validate(verified[0].original)
    variants = tuple(_variant(envelope, baseline, n == 0) for n, envelope in enumerate(verified))
    counts = {}
    for envelope in verified:
        original = originals.Original.model_validate(envelope.original)
        group = counts.setdefault(original.assumptions.currency, [0, 0, 0])
        group[0] += 1
        group[1 if original.projected_gross_minor is not None else 2] += 1
    currencies = tuple(CurrencyGroup(currency=currency, selected_count=values[0], valued_count=values[1],
        unavailable_count=values[2]) for currency, values in sorted(counts.items()))
    return Comparison(institute_id=institute, captured_at=now, baseline_original_id=baseline.id,
        selected_count=len(selected), variants=variants, currencies=currencies)
