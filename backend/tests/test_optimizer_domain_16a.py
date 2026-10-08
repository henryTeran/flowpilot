from datetime import timedelta
from fractions import Fraction
import pytest
from pydantic import ValidationError
from app.modules.optimizer import domain as optimizer
from app.modules.waitlist import domain as matching
from test_waitlist_matching_15a import facts, changed, NOW


def source():
    demand, capture = facts()
    employee = changed(capture.employees[0], employee_id="second")
    return matching.match(demand, changed(capture, employees=[employee, capture.employees[0]]))


def policy(**weights):
    return optimizer.Policy(institute_id="i", id="explicit-policy", captured_at=NOW,
        reason="Explicit human scoring assumptions", weights=[dict(factor=f, value=dict(numerator=str(weights.get(f, 0)), denominator="1")) for f in optimizer.FACTORS])


def evidence(review, **values):
    return tuple(optimizer.Evidence(option=o, constraints=[], factors=[dict(factor=f,
        state="known" if f in values else "unknown", value=dict(numerator=str(values[f][0]), denominator=str(values[f][1])) if f in values else None,
        reference=f"source-{f}" if f in values else None, observed_at=NOW if f in values else None,
        reason="Captured normalized assumption" if f in values else "No source available") for f in optimizer.FACTORS]) for o in review.options)


def result_fraction(score):
    return Fraction(int(score.numerator), int(score.denominator))


def test_exact_weighted_sum_and_penalty_keep_unknown_disabled_factors_explicit():
    review = source()
    result = optimizer.score(review, policy(utilization_score=3, idle_gap_penalty=2),
        evidence(review, utilization_score=(1, 3), idle_gap_penalty=(1, 4)))
    assert result.ranking == "complete"
    assert [r.rank for r in result.options] == [1, 1]
    assert [result_fraction(r.score) for r in result.options] == [Fraction(1, 2)] * 2
    assert all(r.state == "conditional_scored" for r in result.options)
    revenue = result.options[0].contributions[0]
    assert revenue.state == "disabled_by_policy" and revenue.contribution is None
    assert revenue.observation.value is None and revenue.observation.state == "unknown"
    assert result.action == "human_review_then_revalidate_no_booking_or_contact"
    assert any("idle_gap_penalty: -1/2" in r for r in result.options[0].reasons)
    assert {c.id for c in result.options[0].constraints} == {c[0] for c in optimizer.CORE_CONSTRAINTS}
    assert all(c.reference.startswith("source.") and c.observed_at == NOW for c in result.options[0].constraints)


def test_missing_weighted_factor_refuses_entire_ranking_not_zero_or_partial_best():
    review = source()
    rows = list(evidence(review, utilization_score=(1, 2)))
    unknown = optimizer.Observation(factor="utilization_score", state="unknown", value=None,
        reference=None, observed_at=None, reason="No recorded hours")
    rows[0] = changed(rows[0], factors=[unknown if f.factor == unknown.factor else f for f in rows[0].factors])
    result = optimizer.score(review, policy(utilization_score=1), tuple(rows))
    assert result.ranking == "incomplete_evidence"
    assert all(r.rank is None for r in result.options)
    assert sum(r.score is None for r in result.options) == 1
    assert [optimizer.identity(r.option) for r in result.options] == sorted(optimizer.identity(r.option) for r in result.options)


@pytest.mark.parametrize("state", ["unknown", "violated"])
def test_hard_constraint_cannot_be_traded_for_revenue(state):
    review = source()
    rows = evidence(review, revenue_score=(1, 1))
    constraint = optimizer.Constraint(id="workforce-rule", state=state, reference="workforce-source" if state != "unknown" else None,
        observed_at=NOW if state != "unknown" else None, reason="Working-hours rule requires verification")
    rows = tuple(changed(r, constraints=[constraint]) for r in rows)
    result = optimizer.score(review, policy(revenue_score=100), rows)
    assert result.ranking == "no_admissible_options"
    assert all(r.state == "constraint_blocked" and r.score is None and r.rank is None for r in result.options)
    assert all(next(c for c in r.constraints if c.id == "workforce-rule").state == state for r in result.options)


def test_resource_conflict_blocks_even_when_penalty_weight_is_explicitly_zero():
    review = source()
    result = optimizer.score(review, policy(revenue_score=100), evidence(review, revenue_score=(1, 1), resource_conflict_penalty=(1, 2)))
    assert result.ranking == "no_admissible_options"
    assert all(r.constraints[-1].id == "observed_resource_conflict" and r.constraints[-1].state == "violated" for r in result.options)


def test_score_order_exact_ties_and_negative_values_are_deterministic_under_permutation():
    review = source()
    rows = list(evidence(review, idle_gap_penalty=(1, 2)))
    facts = [changed(f, value=dict(numerator="1", denominator="3")) if f.factor == "idle_gap_penalty" else f for f in rows[1].factors]
    rows[1] = changed(rows[1], factors=facts)
    rules = policy(idle_gap_penalty=1)
    result = optimizer.score(review, rules, tuple(rows))
    permuted = optimizer.score(review, changed(rules, weights=list(reversed(rules.weights))),
        tuple(changed(r, factors=list(reversed(r.factors))) for r in reversed(rows)))
    assert result.options == permuted.options
    assert [result_fraction(r.score) for r in result.options] == [Fraction(-1, 3), Fraction(-1, 2)]
    assert [r.rank for r in result.options] == [1, 2]


def test_source_scope_future_policy_and_future_observation_refuse_before_scoring():
    review = source()
    rows = evidence(review, utilization_score=(1, 2))
    for rules in [changed(policy(utilization_score=1), institute_id="foreign"), changed(policy(utilization_score=1), captured_at=NOW+timedelta(microseconds=1))]:
        with pytest.raises(ValueError): optimizer.score(review, rules, rows)
    future = tuple(changed(r, factors=[changed(f, observed_at=NOW+timedelta(microseconds=1)) if f.state == "known" else f for f in r.factors]) for r in rows)
    with pytest.raises(ValueError): optimizer.score(review, policy(utilization_score=1), future)


def test_forged_or_partial_matching_options_and_evidence_never_rewrite_sovereign_admissibility():
    review = source()
    rows = evidence(review, utilization_score=(1, 2))
    forged = changed(review.options[0], employee_id="foreign")
    for altered in [changed(review, options=[forged]), changed(review, options=review.options[:1]), changed(review, unavailable_reason="duration_changed")]:
        with pytest.raises(ValueError): optimizer.score(altered, policy(utilization_score=1), rows)
    for altered in [rows[:1], (*rows, rows[0]), (changed(rows[0], option=forged), rows[1])]:
        with pytest.raises(ValueError): optimizer.score(review, policy(utilization_score=1), altered)


@pytest.mark.parametrize("numerator,denominator", [("-1", "1"), ("1", "0"), ("01", "1"), (1, "1"), ("1", 1)])
def test_ratio_rejects_float_coercion_negative_weights_and_noncanonical_integers(numerator, denominator):
    with pytest.raises(ValidationError): optimizer.Ratio(numerator=numerator, denominator=denominator)


def test_complete_policy_and_known_or_unknown_evidence_require_exact_provenance():
    with pytest.raises(ValueError): policy()
    with pytest.raises(ValueError): changed(policy(utilization_score=1), weights=[policy(utilization_score=1).weights[0]] * 8)
    with pytest.raises(ValueError): optimizer.Observation(factor="revenue_score", state="known", value=dict(numerator="2", denominator="1"), reference="source", observed_at=NOW, reason="Outside normalized scale")
    with pytest.raises(ValueError): optimizer.Observation(factor="revenue_score", state="unknown", value=dict(numerator="0", denominator="1"), reference=None, observed_at=None, reason="Invented zero for absent price")
    review = source()
    unsafe = evidence(review, utilization_score=(1, 2))[0].model_copy(update={"factors": []})
    with pytest.raises(ValueError): optimizer.score(review, policy(utilization_score=1), (unsafe,))


def test_unavailable_core_match_remains_empty_not_a_scored_fallback():
    demand, capture = facts()
    review = matching.match(changed(demand, constraints_review="unknown", constraints_evidence=None), capture)
    result = optimizer.score(review, policy(utilization_score=1), ())
    assert result.ranking == "no_admissible_options" and not result.options
    assert result.source.unavailable_reason == "constraints_unknown"


def test_large_exact_fraction_output_and_reserved_constraint_provenance():
    review = source()
    primes = [1000000007, 1000000009, 1000000033, 1000000087, 1000000093, 1000000097, 1000000103]
    rules = changed(policy(utilization_score=1), weights=[dict(factor=f,
        value=dict(numerator="1", denominator=str(primes[n] if n < 7 else 1))) for n, f in enumerate(optimizer.FACTORS)])
    values = {f: (1, 2**(20+n)) for n, f in enumerate(optimizer.FACTORS[:7])}
    values["resource_conflict_penalty"] = (0, 1)
    result = optimizer.score(review, rules, evidence(review, **values))
    expected = sum((Fraction(-1 if f in optimizer.PENALTIES else 1, primes[n]*values[f][1]) for n, f in enumerate(optimizer.FACTORS[:7])), Fraction())
    assert all(result_fraction(row.score) == expected for row in result.options)
    assert len(result.options[0].score.denominator) > 40
    constraint = optimizer.Constraint(id="observed_resource_conflict", state="satisfied", reference="invented-override",
        observed_at=NOW, reason="Cannot override the reserved hard rule")
    with pytest.raises(ValueError): changed(evidence(review, **values)[0], constraints=[constraint])
