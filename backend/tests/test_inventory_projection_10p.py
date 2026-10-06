from datetime import datetime, timedelta
from decimal import localcontext
import pytest
from app.modules.inventory.projection import ProjectionWindow


def instant(value):
    return datetime.fromisoformat(value)


def window(**changes):
    values = dict(starts_at=instant("2026-10-07T00:00:00+02:00"),
        ends_at=instant("2026-10-08T00:00:00+02:00"),
        observed_starts_at=instant("2026-10-06T00:00:00+02:00"),
        observed_ends_at=instant("2026-10-07T00:00:00+02:00"),
        now=instant("2026-10-07T12:00:00+02:00"))
    return ProjectionWindow.create(**(values | changes))


def test_remaining_horizon_and_half_open_completion_window():
    scope = window()
    assert scope.requested_start == instant("2026-10-06T22:00:00+00:00")
    assert scope.effective_start == scope.generated_at
    assert scope.observed(scope.observed_start)
    assert scope.observed(scope.observed_end - timedelta(microseconds=1))
    assert not scope.observed(scope.observed_end)
    assert not scope.observed(scope.observed_start - timedelta(microseconds=1))
    assert scope.project(4125, "ml") == 2063
    assert scope.project(1000, "unit") == 1000
    assert scope.project(0, "unit") == 0


def test_dst_and_microsecond_projection_uses_elapsed_time_exactly():
    scope = window(starts_at=instant("2026-03-29T00:00:00+01:00"),
        ends_at=instant("2026-03-30T00:00:00+02:00"),
        observed_starts_at=instant("2026-03-28T00:00:00+01:00"),
        observed_ends_at=instant("2026-03-29T00:00:00+01:00"),
        now=instant("2026-03-29T00:00:00+01:00"))
    assert scope.project(24000, "g") == 23000
    tiny = window(starts_at=scope.generated_at, ends_at=scope.generated_at + timedelta(microseconds=3),
        observed_starts_at=scope.generated_at - timedelta(microseconds=7),
        observed_ends_at=scope.generated_at, now=scope.generated_at)
    with localcontext() as context:
        context.prec = 6
        measured = 99999999999999900000
        assert tiny.project(measured, "ml") == (measured * 3 + 6) // 7
        assert tiny.project(measured, "unit") == ((measured * 3 + 6999) // 7000) * 1000


@pytest.mark.parametrize("changes", [
    {"starts_at": datetime(2026, 10, 7)},
    {"now": datetime(2026, 10, 7)},
    {"ends_at": instant("2026-10-07T12:00:00+02:00")},
    {"observed_ends_at": instant("2026-10-07T13:00:00+02:00")},
    {"observed_starts_at": instant("2026-10-07T00:00:00+02:00")},
    {"ends_at": instant("2027-10-09T00:00:00+02:00")},
    {"observed_starts_at": instant("2025-10-05T00:00:00+02:00")},
])
def test_invalid_windows_are_rejected(changes):
    with pytest.raises(ValueError):
        window(**changes)


@pytest.mark.parametrize("quantity,unit", [(-1, "ml"), (True, "ml"),
    (1.0, "g"), (1, "unit"), (1000, "litre")])
def test_invalid_measured_quantities_are_rejected(quantity, unit):
    with pytest.raises(ValueError):
        window().project(quantity, unit)
