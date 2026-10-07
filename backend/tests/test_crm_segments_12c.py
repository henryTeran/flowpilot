from datetime import timedelta

import pytest
from pydantic import ValidationError

from app.modules.crm.metrics import calculate_billing
from app.modules.crm.segments import RegisteredCustomerFact, SegmentPolicy, classify
from test_crm_metrics_12a import NOW, fact, window


def policy(**changes):
    return SegmentPolicy(**dict(dict(institute_id="i", observation_us=86400000000,
        new_customer_us=100, at_risk_us=1000, dormant_us=2000, loyal_min_tickets=2,
        vip_min_tickets=3, vip_currency="CHF", vip_gross_minor="300"), **changes))


def customer(**changes):
    return RegisteredCustomerFact(**dict(dict(institute_id="i", customer_id="customer_a",
        created_at=NOW-timedelta(microseconds=50)), **changes))


def metric(count, age=1, **changes):
    return calculate_billing(window(), [fact(str(i), closed_at=NOW-timedelta(microseconds=age), **changes)
        for i in range(count)])


@pytest.mark.parametrize("count,age,state,reason", [(0, 1, "NEW", "recent_registration"),
    (1, 1, "ACTIVE", "recent_activity"), (2, 1, "LOYAL", "loyal_count"),
    (3, 1, "VIP", "vip_count_and_gross"), (3, 1000, "AT_RISK", "risk_recency"),
    (3, 2000, "DORMANT", "dormant_recency"), (1, 999, "ACTIVE", "recent_activity"),
    (1, 1999, "AT_RISK", "risk_recency")])
def test_six_states_with_exact_boundaries_and_inactivity_priority(count, age, state, reason):
    result = classify(policy(), customer(), metric(count, age), 0)
    assert (result.state, result.reason) == (state, reason)
    assert result.complete_customer_history is False and result.policy == policy()


def test_missing_evidence_never_becomes_dormant_new_or_vip():
    result = classify(policy(), customer(created_at=NOW-timedelta(days=2)), metric(0), 0)
    assert result.state is None and result.reason == "no_observed_closing"
    assert classify(policy(), customer(), metric(0), 1).reason == "undated_closings"
    for changes in ({"currency": None}, {"amount_minor": None, "amount_quality": "missing"},
        {"amount_minor": None, "amount_quality": "invalid"}):
        result = classify(policy(), customer(), metric(3, **changes), 0)
        assert result.state is None and result.reason == "uncertain_vip_gross"
    assert classify(policy(), customer(), metric(3, currency="EUR"), 0).state == "LOYAL"
    assert classify(policy(), customer(), metric(3, amount_minor="99"), 0).state == "LOYAL"
    assert classify(policy(), customer(), metric(3, amount_minor="100"), 0).state == "VIP"
    assert classify(policy(), customer(), metric(2, currency=None), 0).state == "LOYAL"


def test_known_gross_lower_bound_can_prove_vip_without_filling_missing_amounts():
    billing = calculate_billing(window(), [fact("known", amount_minor="300"),
        fact("unknown", currency=None), fact("missing", amount_minor=None, amount_quality="missing")])
    assert classify(policy(), customer(), billing, 0).state == "VIP"
    assert billing.currencies[0].recorded_average_basket_minor is None


def test_registration_age_and_stale_read_boundaries():
    assert classify(policy(), customer(created_at=NOW-timedelta(microseconds=100)), metric(0), 0).state == "NEW"
    assert classify(policy(), customer(created_at=NOW-timedelta(microseconds=101)), metric(0), 0).state is None
    old = calculate_billing(window(start=NOW-timedelta(days=1, microseconds=1),
        end=NOW-timedelta(microseconds=1)), [])
    assert classify(policy(), customer(), old, 0).reason == "stale_window"


def test_scope_capture_horizon_and_diagnostic_refusals():
    for wrong in (customer(institute_id="other"), customer(customer_id="other"),
        customer(created_at=NOW+timedelta(microseconds=1))):
        with pytest.raises(ValueError):
            classify(policy(), wrong, metric(1), 0)
    for changes in ({"institute_id": "other"}, {"observation_us": 86400000001}):
        with pytest.raises(ValueError):
            classify(policy(**changes), customer(), metric(1), 0)
    for count in (True, -1, "0", None):
        with pytest.raises(ValueError):
            classify(policy(), customer(), metric(1), count)


@pytest.mark.parametrize("changes", [{"at_risk_us": 2000}, {"dormant_us": 86400000000},
    {"new_customer_us": 86400000001}, {"vip_min_tickets": 2}, {"loyal_min_tickets": 0},
    {"vip_min_tickets": True}, {"vip_gross_minor": "01"}, {"vip_currency": "USD"},
    {"at_risk_us": "1000"}, {"observation_us": 0}])
def test_policy_has_no_coerced_or_unreachable_thresholds(changes):
    with pytest.raises(ValidationError):
        policy(**changes)
