from datetime import timedelta
from fractions import Fraction
import pytest
from app.modules.optimizer import domain, policy
from test_waitlist_matching_15a import NOW
from test_optimizer_domain_16a import source as matching_source


def rule(factor="revenue_score", enabled=True, **changes):
    values = dict(factor=factor, weight=dict(numerator="1" if enabled else "0", denominator="1"), basis=policy.BASES[factor] if enabled else "disabled",
        ceiling="10000" if enabled and factor == "revenue_score" else "60000000" if enabled and factor in {"idle_gap_penalty", "overtime_penalty"} else None,
        currency="CHF" if enabled and factor == "revenue_score" else None, price_mode="member" if enabled and factor == "revenue_score" else None,
        reason="Explicit normalization assumptions")
    return policy.Rule.model_validate({**values, **changes})


def fact(factor="revenue_score", quantity="2500", **changes):
    values = dict(factor=factor, basis=policy.BASES[factor], quantity=quantity,
        denominator="120000000" if factor == "utilization_score" and quantity is not None else None,
        currency="CHF" if factor == "revenue_score" and quantity is not None else None, price_mode="member" if factor == "revenue_score" and quantity is not None else None,
        reference="owned-source" if quantity is not None else None, observed_at=NOW if quantity is not None else None, reason="Captured raw source quantity")
    return policy.Source.model_validate({**values, **changes})


def test_exact_reference_normalization_and_explicit_saturation_keep_raw_value():
    result = policy.normalize(rule(), fact(), NOW)
    assert result.observation.value.fraction() == Fraction(1, 4)
    assert result.source.quantity == "2500" and result.rule.ceiling == "10000" and result.saturated == "no"
    result = policy.normalize(rule(), fact(quantity="25000"), NOW)
    assert result.observation.value.fraction() == 1 and result.saturated == "yes"
    assert result.source.quantity == "25000"  # Not a quote/profit/lift or rewritten source.


@pytest.mark.parametrize("factor", domain.FACTORS)
def test_missing_source_stays_unknown_for_every_weighted_factor(factor):
    result = policy.normalize(rule(factor), fact(factor, quantity=None), NOW)
    assert result.observation.state == "unknown" and result.observation.value is None
    assert result.observation.reference is None and result.saturated == "not_computed"


def test_disabled_revenue_keeps_raw_trace_without_inventing_a_normalized_zero():
    result = policy.normalize(rule(enabled=False), fact(), NOW)
    assert result.source.quantity == "2500" and result.observation.state == "unknown"
    assert result.rule.ceiling is None and result.observation.value is None


def test_elapsed_unit_and_utilization_ratio_are_exact_and_not_wall_clock_minutes():
    value = policy.normalize(rule("idle_gap_penalty"), fact("idle_gap_penalty", quantity="15000001"), NOW)
    assert value.observation.value.fraction() == Fraction(15000001, 60000000)
    value = policy.normalize(rule("utilization_score"), fact("utilization_score", quantity="30000000"), NOW)
    assert value.observation.value.fraction() == Fraction(1, 4)
    with pytest.raises(ValueError): fact("utilization_score", quantity="120000001")


@pytest.mark.parametrize("field,value", [("ceiling", None), ("currency", None), ("price_mode", None), ("basis", "elapsed_start_delay")])
def test_enabled_monetary_rule_requires_all_explicit_normalization_terms(field, value):
    with pytest.raises(ValueError): rule(**{field: value})


def test_disabled_and_nonmonetary_rules_refuse_hidden_assumptions():
    with pytest.raises(ValueError): rule(enabled=False, ceiling="100")
    with pytest.raises(ValueError): rule("utilization_score", ceiling="100")
    with pytest.raises(ValueError): rule("idle_gap_penalty", currency="CHF")
    with pytest.raises(ValueError): rule("overtime_penalty", ceiling=None)


def test_source_factor_basis_currency_mode_and_future_capture_are_bound():
    with pytest.raises(ValueError): policy.normalize(rule(), fact(currency="EUR"), NOW)
    with pytest.raises(ValueError): policy.normalize(rule(), fact(price_mode="passage"), NOW)
    with pytest.raises(ValueError): policy.normalize(rule(), fact(observed_at=NOW+timedelta(microseconds=1)), NOW)
    with pytest.raises(ValueError): policy.normalize(rule(), fact(), NOW.replace(tzinfo=None))
    with pytest.raises(ValueError): fact("continuity_score", quantity="1", basis="catalog_reference")
    with pytest.raises(ValueError): fact(quantity=None, reference="invented")
    with pytest.raises(ValueError): fact("continuity_score", quantity="2")


def test_disabled_conflict_weight_cannot_hide_a_known_hard_conflict_from_scoring():
    conflict = policy.normalize(rule("resource_conflict_penalty", enabled=False), fact("resource_conflict_penalty", quantity="1"), NOW)
    assert conflict.observation.state == "known" and conflict.observation.value.fraction() == 1
    terms = policy.Terms(rules=[rule(f, enabled=f == "utilization_score") for f in domain.FACTORS])
    scoring = policy.scoring_policy(terms, "i", "policy", NOW, "Explicit captured policy")
    review = matching_source()
    observations = tuple(policy.normalize(next(r for r in terms.rules if r.factor == f),
        fact(f, quantity="1" if f == "resource_conflict_penalty" else "30000000" if f == "utilization_score" else None), NOW).observation for f in domain.FACTORS)
    result = domain.score(review, scoring, tuple(domain.Evidence(option=o, factors=observations, constraints=()) for o in review.options))
    assert result.ranking == "no_admissible_options" and all(o.score is None for o in result.options)


def test_complete_terms_preserve_explicit_weights_and_reject_duplicate_or_empty_policy():
    terms = policy.Terms(rules=[rule(f, enabled=f == "utilization_score") for f in reversed(domain.FACTORS)])
    result = policy.scoring_policy(terms, "i", "policy", NOW, "Explicit captured policy")
    assert [w.factor for w in result.weights] == list(domain.FACTORS)
    assert sum(w.value.fraction() for w in result.weights) == 1
    with pytest.raises(ValueError): policy.Terms(rules=[rule(enabled=False)]*8)
    with pytest.raises(ValueError): policy.Terms(rules=[rule(f, enabled=False) for f in domain.FACTORS])
    unsafe = rule().model_copy(update={"ceiling": None})
    with pytest.raises(ValueError): policy.normalize(unsafe, fact(), NOW)
