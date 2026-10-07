from datetime import datetime, timedelta, timezone
from fractions import Fraction

import pytest
from pydantic import ValidationError

from app.modules.crm.lifetime import LifetimeAssumptions, calculate_remaining_lifetime
from app.modules.crm.metrics import BillingWindow, ClosedTicketFact, calculate_billing

NOW = datetime(2026, 10, 7, tzinfo=timezone.utc)


def assumptions(**changes):
    return LifetimeAssumptions(**dict(dict(institute_id="i", customer_id="customer_a",
        model="constant_observed_rate_finite_remaining_lifetime_undiscounted_v1", currency="CHF",
        expected_active_us="172800000000", activity_fraction={"numerator": "1", "denominator": "2"},
        gross_contribution_margin={"numerator": "1", "denominator": "3"}, future_relationship_cost_minor="100"), **changes))


def billing(entries=("101",), **window_changes):
    window = BillingWindow(**dict(dict(institute_id="i", customer_id="customer_a", start=NOW-timedelta(days=1), end=NOW, captured_at=NOW), **window_changes))
    return calculate_billing(window, [ClosedTicketFact(institute_id="i", customer_id="customer_a", ticket_id=f"t{i}",
        captured_at=window.captured_at, closed_at=window.end-timedelta(microseconds=1), currency="CHF",
        amount_minor=amount, amount_quality="known" if amount is not None else "missing") for i, amount in enumerate(entries)])


def test_exact_remaining_scenario_preserves_negative_value_and_provenance():
    source = billing(); declared = assumptions()
    result = calculate_remaining_lifetime(declared, source, 0, 0)
    assert result.projected_gross_minor.model_dump() == {"numerator": "101", "denominator": "1"}
    assert result.projected_contribution_minor.model_dump() == {"numerator": "101", "denominator": "3"}
    assert result.remaining_clv_minor.model_dump() == {"numerator": "-199", "denominator": "3"}
    assert result.assumed_active_until == NOW+timedelta(days=2)
    assert result.assumptions == declared and result.billing == source
    assert source.predicted_clv is None and result.unavailable_reason is None
    assert not result.complete_customer_history and not result.validated_prediction and not result.discounted


def test_fractional_duration_and_large_integer_cost_never_use_float_or_json_numbers():
    r = calculate_remaining_lifetime(assumptions(expected_active_us="1", future_relationship_cost_minor="9007199254740993"), billing(), 0, 0)
    expected = Fraction(101,86400000000*6)-9007199254740993
    assert r.remaining_clv_minor.numerator == str(expected.numerator)
    assert r.remaining_clv_minor.denominator == str(expected.denominator)
    assert isinstance(r.model_dump(mode="json")["remaining_clv_minor"]["numerator"],str)


def test_offset_aliases_and_calendar_boundary_preserve_actual_duration():
    alias = NOW.astimezone(timezone(timedelta(hours=2)))
    r = calculate_remaining_lifetime(assumptions(),billing(start=(NOW-timedelta(days=1)).astimezone(timezone(timedelta(hours=-3))),end=alias,captured_at=alias),0,0)
    assert r.projected_gross_minor.numerator == "101" and r.assumed_active_until == NOW+timedelta(days=2)
    last = datetime(9999,12,31,23,59,59,999999,tzinfo=timezone.utc)
    r = calculate_remaining_lifetime(assumptions(expected_active_us="1"),billing(start=last-timedelta(days=1),end=last,captured_at=last),0,0)
    assert r.unavailable_reason == "unrepresentable_lifetime" and r.assumed_active_until is None


@pytest.mark.parametrize("changes", [{"expected_active_us": "0"}, {"expected_active_us": 1},
    {"expected_active_us": "01"}, {"expected_active_us": "9"*31}, {"future_relationship_cost_minor": "-1"},
    {"activity_fraction": {"numerator": "2", "denominator": "1"}},
    {"gross_contribution_margin": {"numerator": "1", "denominator": "0"}},
    {"gross_contribution_margin": {"numerator": True, "denominator": "1"}},
    {"model": "learned_forecast"}, {"currency": "USD"}, {"customer_id": " customer_a"}])
def test_no_coerced_or_implicit_assumptions(changes):
    with pytest.raises(ValidationError): assumptions(**changes)


def test_no_missing_default_and_no_cross_scope_or_coerced_diagnostics():
    terms = assumptions().model_dump(); del terms["activity_fraction"]
    with pytest.raises(ValidationError): LifetimeAssumptions(**terms)
    for change in ({"institute_id": "other"}, {"customer_id": "other"}):
        with pytest.raises(ValueError): calculate_remaining_lifetime(assumptions(**change),billing(),0,0)
    for bad in (True, -1, "0", 0.0):
        with pytest.raises(ValueError): calculate_remaining_lifetime(assumptions(),billing(),bad,0)
        with pytest.raises(ValueError): calculate_remaining_lifetime(assumptions(),billing(),0,bad)


@pytest.mark.parametrize("source,undated,future,terms,reason", [
    (billing(end=NOW-timedelta(seconds=1)),0,0,{},"stale_window"),
    (billing(),1,1,{},"undated_closings"), (billing(),0,1,{},"future_closings"),
    (billing(),0,0,{"expected_active_us":"9"*30},"unrepresentable_lifetime"),
    (billing(()),0,0,{},"no_observed_currency"), (billing((None,"101")),0,0,{},"uncertain_amounts"),
    (billing(),0,0,{"currency":"EUR"},"no_observed_currency")])
def test_uncertainty_never_projects_a_favorable_subset(source,undated,future,terms,reason):
    r = calculate_remaining_lifetime(assumptions(**terms),source,undated,future)
    assert r.unavailable_reason == reason
    assert r.projected_gross_minor is r.projected_contribution_minor is r.remaining_clv_minor is None


def test_currency_separation_unknown_currency_and_explicit_zero():
    window = billing().window
    def fact(key,currency,amount):
        return ClosedTicketFact(institute_id="i",customer_id="customer_a",ticket_id=key,closed_at=NOW-timedelta(microseconds=1),
            captured_at=NOW,currency=currency,amount_minor=amount,amount_quality="known")
    mixed = calculate_billing(window,[fact("a","CHF","101"),fact("b","EUR","9999999999")])
    assert calculate_remaining_lifetime(assumptions(),mixed,0,0).projected_gross_minor.numerator == "101"
    unknown = calculate_billing(window,[fact("a","CHF","101"),fact("b",None,"1")])
    r = calculate_remaining_lifetime(assumptions(),unknown,0,0)
    assert r.unavailable_reason == "unknown_currency" and r.remaining_clv_minor is None
    zero = calculate_remaining_lifetime(assumptions(),billing(("0",)),0,0)
    assert zero.projected_gross_minor.numerator == "0" and zero.remaining_clv_minor.numerator == "-100"
    inactive = calculate_remaining_lifetime(assumptions(activity_fraction={"numerator":"0","denominator":"1"}),billing(),0,0)
    assert inactive.remaining_clv_minor.numerator == "-100"
