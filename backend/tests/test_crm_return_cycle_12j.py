from datetime import timedelta
import pytest
from pydantic import ValidationError
from app.modules.crm.return_cycle import CompletedCareFact, calculate
from test_crm_metrics_12a import NOW, window


def care(source="s", ticket="t", first=20, last=10, **changes):
    return CompletedCareFact(**dict(dict(institute_id="i", customer_id="customer_a", ticket_id=ticket,
        source_kind="session", source_id=source, service_id="care_a", actual_start_at=NOW-timedelta(microseconds=first),
        actual_end_at=NOW-timedelta(microseconds=last), captured_at=NOW), **changes))


def test_shared_ticket_care_is_one_episode_and_exact_return_gap_is_not_a_booking_credit():
    facts = [care("first", first=100, last=90), care("second", first=80, last=70, service_id="care_b"),
        care("return", "next", first=51, last=40, source_kind="appointment")]
    result = calculate(window(), reversed(facts))
    assert result.execution_count == 3 and result.episode_count == 2
    assert result.episodes[0].service_ids == ("care_a", "care_b")
    assert result.episodes[0].execution_count == 2
    assert result.gaps[0].gap_us == "19"
    assert result.average_return_gap_us.model_dump() == {"numerator": "19", "denominator": "1"}
    assert not result.complete_customer_history and not result.inferred_booking_credit


def test_empty_single_and_overlapping_episodes_do_not_fabricate_a_cycle():
    for facts in ([], [care()]):
        result = calculate(window(), facts)
        assert result.average_return_gap_us is None and result.known_gap_total_us == "0"
    result = calculate(window(), [care("a", "one", first=100, last=50),
        care("b", "two", first=70, last=40), care("c", "three", first=30, last=20)])
    assert result.overlapping_gap_count == 1 and result.known_gap_count == 1
    assert result.known_gap_total_us == "10" and result.average_return_gap_us is None
    assert result.gaps[0].quality == "overlapping_episodes" and result.gaps[0].gap_us is None


def test_fractional_mean_preserves_exact_microseconds_without_rounding():
    result = calculate(window(), [care("a", "one", first=100, last=90),
        care("b", "two", first=71, last=60), care("c", "three", first=40, last=30)])
    assert result.known_gap_count == 2 and result.known_gap_total_us == "39"
    assert result.average_return_gap_us.model_dump() == {"numerator": "39", "denominator": "2"}


def test_half_open_scope_capture_uniqueness_and_zero_gap():
    assert calculate(window(), [care(actual_end_at=window().start, actual_start_at=window().start-timedelta(microseconds=1))]).episode_count == 1
    for changes in ({"institute_id": "other"}, {"customer_id": "other"}, {"captured_at": NOW+timedelta(microseconds=1)},
        {"actual_end_at": NOW}, {"actual_end_at": window().start-timedelta(microseconds=1), "actual_start_at": window().start-timedelta(microseconds=2)}):
        with pytest.raises(ValueError): calculate(window(), [care(**changes)])
    with pytest.raises(ValueError): calculate(window(), [care(), care()])
    result = calculate(window(), [care("a", "one", first=30, last=20), care("b", "two", first=20, last=10)])
    assert result.average_return_gap_us.numerator == "0"
    assert calculate(window(), [care(), care(source_kind="appointment")]).execution_count == 2


@pytest.mark.parametrize("changes", [{"actual_start_at": NOW}, {"actual_end_at": NOW+timedelta(microseconds=1)},
    {"actual_start_at": NOW.replace(tzinfo=None)}, {"actual_end_at": 1}, {"source_kind": "paid_ticket"}])
def test_nonactual_or_incoherent_source_is_refused(changes):
    with pytest.raises(ValidationError): care(**changes)
