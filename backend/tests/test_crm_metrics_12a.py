from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.modules.crm.metrics import BillingWindow, ClosedTicketFact, calculate_billing


NOW = datetime(2026, 10, 7, tzinfo=timezone.utc)


def window(**changes):
    return BillingWindow(**dict(dict(institute_id="i", customer_id="customer_a",
        start=NOW-timedelta(days=1), end=NOW, captured_at=NOW), **changes))


def fact(ticket="t", **changes):
    return ClosedTicketFact(**dict(dict(institute_id="i", customer_id="customer_a",
        ticket_id=ticket, closed_at=NOW-timedelta(microseconds=1), captured_at=NOW,
        currency="CHF", amount_minor="101", amount_quality="known"), **changes))


def test_empty_history_is_unknown_not_a_prediction():
    result = calculate_billing(window(), [])
    assert result.closed_tickets == 0
    assert result.frequency_per_microsecond.model_dump() == {"numerator": "0", "denominator": 86400000000}
    assert result.last_recorded_closed_at is None and result.recorded_recency_us is None
    assert result.currencies == () and result.predicted_clv is None
    assert result.complete_customer_history is False


def test_exact_currency_cohorts_and_missing_sources():
    result = calculate_billing(window(), [fact(), fact("t2", amount_minor="100"),
        fact("t3", currency="EUR", amount_minor="9999999999"),
        fact("t4", currency="EUR", amount_minor=None, amount_quality="missing"),
        fact("t5", currency=None),
        fact("t6", currency="EUR", amount_minor=None, amount_quality="invalid")])
    chf, eur = result.currencies
    assert chf.known_gross_minor == "201"
    assert chf.recorded_average_basket_minor.model_dump() == {"numerator": "201", "denominator": 2}
    assert eur.known_gross_minor == "9999999999" and eur.recorded_average_basket_minor is None
    assert (eur.known_amount_tickets, eur.missing_amount_tickets, eur.invalid_amount_tickets) == (1, 1, 1)
    assert result.closed_tickets == 6 and result.recorded_recency_us == "1"
    assert result.unknown_currency_tickets == 1 and not result.complete_currency_classification


def test_half_open_scope_capture_and_uniqueness():
    assert calculate_billing(window(), [fact(closed_at=window().start)]).closed_tickets == 1
    for changes in ({"closed_at": NOW}, {"closed_at": window().start-timedelta(microseconds=1)},
        {"institute_id": "other"}, {"customer_id": "customer_b"},
        {"captured_at": NOW+timedelta(microseconds=1)}):
        with pytest.raises(ValueError):
            calculate_billing(window(), [fact(**changes)])
    with pytest.raises(ValueError):
        calculate_billing(window(), [fact(), fact()])
    equivalent = fact(captured_at=NOW.astimezone(timezone(timedelta(hours=2))))
    assert calculate_billing(window(), [equivalent]).recorded_recency_us == "1"


@pytest.mark.parametrize("changes", [{"amount_minor": "01"}, {"amount_minor": "-1"},
    {"amount_minor": "1.5"}, {"amount_minor": 12}, {"amount_minor": "10000000000"},
    {"amount_minor": None}, {"amount_quality": "missing"}, {"currency": "USD"},
    {"closed_at": 1}, {"closed_at": NOW.replace(tzinfo=None)},
    {"closed_at": NOW+timedelta(microseconds=1)}, {"customer_id": " customer_a"}])
def test_invalid_source_is_refused(changes):
    with pytest.raises(ValidationError):
        fact(**changes)


def test_exact_microsecond_window_and_zero_gross():
    result = calculate_billing(window(start=NOW-timedelta(microseconds=1)), [fact(amount_minor="0")])
    assert result.frequency_per_microsecond.denominator == 1
    assert result.currencies[0].recorded_average_basket_minor.numerator == "0"
    for changes in ({"start": NOW}, {"end": NOW+timedelta(microseconds=1)}, {"start": "2026-10-06"}):
        with pytest.raises(ValidationError):
            window(**changes)
