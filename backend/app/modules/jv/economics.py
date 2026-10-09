"""Exact observed-period differences, never causal attribution or forecasts."""
from fractions import Fraction
from datetime import datetime
from typing import Annotated, Literal
from pydantic import AwareDatetime, StringConstraints, model_validator, field_validator
from app.modules.crm.metrics import Fact, Unsigned
from app.modules.base.read_capabilities import Digest, ExactId
from app.modules.revenue import billing, sources
from app.modules.jv.operational import Citation
from app.modules.waitlist.originals import fingerprint


class Request(Fact):
    baseline_start: AwareDatetime
    baseline_end: AwareDatetime
    current_start: AwareDatetime
    current_end: AwareDatetime

    @field_validator("*", mode="before")
    @classmethod
    def explicit_instant(cls, value):
        if not isinstance(value, (str, datetime)) or isinstance(value, str) and "T" not in value:
            raise ValueError("Explicit aware ISO periods are required")
        return value

    @model_validator(mode="after")
    def ordered(self):
        if not self.baseline_start < self.baseline_end <= self.current_start < self.current_end:
            raise ValueError("Two positive ordered nonoverlapping observed periods are required")
        return self


Signed = Annotated[str, StringConstraints(pattern=r"^(0|-?[1-9][0-9]*)$")]


class Ratio(Fact):
    numerator: Signed
    denominator: Annotated[str, StringConstraints(pattern=r"^[1-9][0-9]*$")]


class CurrencyDifference(Fact):
    currency: Literal["CHF", "EUR"]
    baseline_gross_minor: Unsigned | None
    current_gross_minor: Unsigned | None
    difference_minor: Signed | None
    percent_change: Ratio | None
    unavailable_reason: Literal["unknown_currency", "incomplete_amounts", "zero_baseline"] | None
    sources: tuple[Citation, ...]


class Analysis(Fact):
    institute_id: ExactId
    evidence_fingerprint: Digest
    rule_version: Literal["jv.recorded_billing_comparison.v1"] = "jv.recorded_billing_comparison.v1"
    ticket_count_difference: int
    currencies: tuple[CurrencyDifference, ...]
    same_elapsed_duration: bool
    diagnostics: tuple[Literal["unequal_period_durations", "unknown_currency", "incomplete_amounts", "undated_paid_tickets"], ...]
    causal_contributions: tuple[()] = ()
    missing_facts: tuple[str, ...] = ("causal_attribution", "complete_sales_history", "settlement_confirmation")
    actions: tuple[()] = ()
    basis: Literal["recorded_dated_paid_totals_no_duration_adjustment_or_currency_conversion"] = "recorded_dated_paid_totals_no_duration_adjustment_or_currency_conversion"
    fingerprint: Digest


class Capture(Fact):
    baseline: billing.Billing
    current: billing.Billing


class Response(Fact):
    source: Capture
    analysis: Analysis


def analyze(candidate: Capture) -> Analysis:
    capture = Capture.model_validate(candidate.model_dump(mode="json"))
    baseline, current = capture.baseline, capture.current
    if baseline.window.institute_id != current.window.institute_id or not baseline.window.end <= current.window.start:
        raise ValueError("JV billing scope/period mismatch")
    digest = fingerprint(capture.model_dump(mode="json"))
    same = baseline.window.end - baseline.window.start == current.window.end - current.window.start
    diagnostics = [] if same else ["unequal_period_durations"]
    if any(g.currency is None for value in (baseline, current) for g in value.ticket_amounts):
        diagnostics.append("unknown_currency")
    if any(g.missing_amount_count or g.invalid_amount_count for value in (baseline, current) for g in value.ticket_amounts):
        diagnostics.append("incomplete_amounts")
    if baseline.institute_undated_paid_tickets or current.institute_undated_paid_tickets:
        diagnostics.append("undated_paid_tickets")
    currencies = sorted({g.currency for value in (baseline, current) for g in value.ticket_amounts if g.currency})
    differences = []
    for currency in currencies:
        gross = []
        for value in (baseline, current):
            group = next((g for g in value.ticket_amounts if g.currency == currency), None)
            gross.append(group.complete_gross_minor if group else "0")
        reason = "unknown_currency" if "unknown_currency" in diagnostics else "incomplete_amounts" if any(v is None for v in gross) else None
        difference = percentage = None
        if reason is None:
            difference = str(int(gross[1]) - int(gross[0]))
            if int(gross[0]):
                exact = Fraction(int(difference) * 100, int(gross[0]))
                percentage = Ratio(numerator=str(exact.numerator), denominator=str(exact.denominator))
            else:
                reason = "zero_baseline"
        differences.append(CurrencyDifference(currency=currency, baseline_gross_minor=gross[0], current_gross_minor=gross[1],
            difference_minor=difference, percent_change=percentage, unavailable_reason=reason,
            sources=tuple(Citation(evidence_fingerprint=digest, pointer=f"/{period}/ticket_amounts") for period in ("baseline", "current"))))
    result = Analysis(institute_id=baseline.window.institute_id, evidence_fingerprint=digest,
        ticket_count_difference=current.ticket_count-baseline.ticket_count, currencies=tuple(differences),
        same_elapsed_duration=same, diagnostics=tuple(diagnostics), fingerprint="0" * 64)
    return result.model_copy(update={"fingerprint": fingerprint(result.model_dump(mode="json", exclude={"fingerprint"}))})


def read(db, institute, request: Request) -> Response:
    source = Capture(baseline=sources.read(db, institute, request.baseline_start, request.baseline_end),
        current=sources.read(db, institute, request.current_start, request.current_end))
    return Response(source=source, analysis=analyze(source))
