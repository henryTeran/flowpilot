from datetime import datetime, timedelta, timezone
from decimal import localcontext
import pytest
from app.modules.revenue.billing import Window, TicketFact, LineFact, calculate


NOW = datetime(2026, 1, 3, tzinfo=timezone.utc)
WINDOW = Window(institute_id="own", start=NOW-timedelta(days=2), end=NOW, captured_at=NOW)


def ticket(identifier="ticket", currency="CHF", amount="100", quality="known"):
    return TicketFact(institute_id="own", ticket_id=identifier, paid_at=NOW-timedelta(days=1), captured_at=NOW,
        currency=currency, amount_minor=amount, amount_quality=quality)


def line(identifier="line", parent="ticket", category="care", units=1, amount="100", quality="known"):
    return LineFact(institute_id="own", ticket_id=parent, line_id=identifier, service_id="service", captured_at=NOW,
        category=category, quantity=units, amount_minor=amount, amount_quality=quality)


def test_exact_currency_baskets_mix_and_retail_do_not_double_count_quantities():
    result = calculate(WINDOW, [ticket(), ticket("second", amount="101"), ticket("eur", "EUR", "999")],
        [line(), line("retail", category="retail", units=3, amount="30"), line("second-care", "second"), line("eur-care", "eur")])
    chf = result.ticket_amounts[0]
    assert chf.complete_gross_minor == "201" and chf.average_minor.numerator == "201" and chf.average_minor.denominator == "2"
    assert result.ticket_count == 3 and result.active_line_count == 4
    assert result.recorded_retail_attach_ratio.numerator == "1" and result.recorded_retail_attach_ratio.denominator == "3"
    retail = next(group for group in result.service_mix if group.category == "retail")
    assert retail.units == "3" and retail.amounts.known_gross_minor == "30"  # line total already includes quantity
    assert not result.complete_sales_history and not result.settlement_confirmed and result.projected_revenue is None


def test_incomplete_classification_and_amounts_never_become_zero_or_full_average():
    result = calculate(WINDOW, [ticket(), ticket("missing", amount=None, quality="missing"),
        ticket("invalid", amount=None, quality="invalid"), ticket("unknown", None, "12")], [line(category=None)])
    unknown, chf = result.ticket_amounts
    assert unknown.known_gross_minor == "12" and unknown.complete_gross_minor is None and unknown.average_minor is None
    assert chf.known_gross_minor == "100" and chf.complete_gross_minor is None and chf.average_minor is None
    assert chf.missing_amount_count == 1 and chf.invalid_amount_count == 1
    assert result.tickets_without_active_lines == 3 and result.tickets_with_unknown_category == 1
    assert result.recorded_retail_attach_ratio is None


def test_large_totals_and_average_are_exact_under_small_decimal_context():
    with localcontext() as context:
        context.prec = 2
        result = calculate(WINDOW, (ticket(str(i), amount="9999999999") for i in range(25)), [])
    group = result.ticket_amounts[0]
    assert group.known_gross_minor == "249999999975" and group.average_minor.denominator == "25"


@pytest.mark.parametrize("update", [dict(institute_id="foreign"), dict(captured_at=NOW+timedelta(microseconds=1)),
    dict(paid_at=WINDOW.end), dict(paid_at=WINDOW.start-timedelta(microseconds=1)), dict(amount_minor="-1"),
    dict(amount_quality="missing"), dict(paid_at=NOW.replace(tzinfo=None))])
def test_substituted_ticket_scope_clock_window_and_unsafe_models_refused(update):
    with pytest.raises(ValueError): calculate(WINDOW, [ticket().model_copy(update=update)], [])


def test_duplicate_or_foreign_lines_and_tickets_refuse_instead_of_counting_twice():
    with pytest.raises(ValueError): calculate(WINDOW, [ticket(), ticket()], [])
    for rows in ([line(), line()], [line(parent="other")], [line().model_copy(update=dict(quantity=True))],
        [line().model_copy(update=dict(institute_id="foreign"))], [line().model_copy(update=dict(captured_at=NOW-timedelta(seconds=1)))]):
        with pytest.raises(ValueError): calculate(WINDOW, [ticket()], rows)
    empty = calculate(WINDOW, [], [])
    assert empty.ticket_count == 0 and empty.ticket_amounts == () and empty.recorded_retail_attach_ratio is None


def test_non_boolean_no_claim_flags_and_blank_source_identifiers_refused():
    result = calculate(WINDOW, [], []).model_dump()
    from app.modules.revenue.billing import Billing
    for name in ("complete_sales_history", "settlement_confirmed"):
        for value in (0, "false", True):
            with pytest.raises(ValueError): Billing.model_validate({**result, name: value})
    with pytest.raises(ValueError): calculate(WINDOW, [ticket()], [line().model_copy(update=dict(line_id=" line "))])
