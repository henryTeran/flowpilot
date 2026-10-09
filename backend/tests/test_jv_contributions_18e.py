"""Exact reconciliation and unknowns; accounting identities are not causes."""
from fractions import Fraction
from decimal import localcontext
import pytest
from app.modules.jv import economics
from test_jv_economics_18d import capture


def amount(value):
    return Fraction(int(value.numerator), int(value.denominator))


def test_volume_and_basket_can_offset_and_reconcile_exactly_per_currency():
    source = capture([("CHF", "100"), ("CHF", "101"), ("EUR", "1000")],
        [("CHF", "120"), ("CHF", "120"), ("CHF", "120"), ("EUR", "900")])
    with localcontext() as context:
        context.prec = 2
        result = economics.analyze(source)
    chf, eur = result.currencies
    assert amount(chf.decomposition.volume_term_minor) == Fraction(201, 2)
    assert amount(chf.decomposition.basket_term_minor) == Fraction(117, 2)
    assert amount(eur.decomposition.volume_term_minor) == 0
    assert amount(eur.decomposition.basket_term_minor) == -100
    assert result.causal_contributions == ()
    for currency in result.currencies:
        assert amount(currency.decomposition.volume_term_minor)+amount(currency.decomposition.basket_term_minor) == int(currency.difference_minor)


def test_empty_current_and_observed_zero_baseline_amount_have_exact_terms():
    result = economics.analyze(capture([("CHF", "101")], [] )).currencies[0]
    assert amount(result.decomposition.volume_term_minor) == -101
    assert amount(result.decomposition.basket_term_minor) == 0
    result = economics.analyze(capture([("CHF", "0")], [("CHF", "100")])).currencies[0]
    assert result.percent_change is None and result.unavailable_reason == "zero_baseline"
    assert amount(result.decomposition.volume_term_minor) == 0 and amount(result.decomposition.basket_term_minor) == 100


def test_no_baseline_ticket_and_incomplete_facts_do_not_become_averages():
    for source, reason in [(capture([], [("CHF", "100")]), "no_baseline_tickets"),
        (capture([("CHF", None)], [("CHF", "100")]), "incomplete_amounts"),
        (capture([(None, "100")], [("CHF", "100")]), "unknown_currency")]:
        result = economics.analyze(source).currencies[0]
        assert result.decomposition is None and result.decomposition_unavailable_reason == reason


def test_fabricated_offsetting_terms_cannot_pass_even_when_sum_is_correct():
    result = economics.analyze(capture([("CHF", "100")], [("CHF", "200")])).currencies[0]
    raw = result.model_dump(mode="json")
    raw["decomposition"]["volume_term_minor"]["numerator"] = "500"
    raw["decomposition"]["basket_term_minor"]["numerator"] = "-400"
    with pytest.raises(ValueError, match="accounting terms"):
        economics.CurrencyDifference.model_validate(raw)
