from datetime import datetime, timedelta, timezone
import pytest
from app.modules.workforce.interval_math import union_intervals, intersection_duration

ORIGIN = datetime(2025, 10, 26, tzinfo=timezone.utc)


def ranges(values):
    return ((ORIGIN+timedelta(microseconds=start), ORIGIN+timedelta(microseconds=end)) for start, end in values)


def test_exact_occupation_intersection_merges_overlap_and_preserves_breaks_and_microseconds():
    work = union_intervals(ranges([(0, 10), (5, 20), (20, 30), (40, 50)]))
    busy = union_intervals(ranges([(-5, 1), (1, 15), (10, 25), (35, 45), (44, 55)]))
    assert intersection_duration(work, busy) == 35
    assert intersection_duration(union_intervals(ranges([])), union_intervals(ranges([(0, 100)]))) == 0
    assert intersection_duration(union_intervals(ranges([(0, 1)])), union_intervals(ranges([(1, 2)]))) == 0


def test_union_rejects_nonpositive_or_unordered_sources():
    for values in [[(1, 1)], [(2, 1)], [(5, 10), (0, 6)], [(0, 10), (5, 8), (4, 6)]]:
        with pytest.raises(ValueError):
            list(union_intervals(ranges(values)))


def test_union_intersection_matches_a_bruteforce_microsecond_oracle():
    import random
    generator = random.Random(11)
    for _ in range(100):
        left = sorted((start, start+generator.randrange(1, 20)) for start in (generator.randrange(-20, 80) for _ in range(20)))
        right = sorted((start, start+generator.randrange(1, 20)) for start in (generator.randrange(-20, 80) for _ in range(20)))
        expected = len(set().union(*(set(range(a, b)) for a, b in left)) & set().union(*(set(range(a, b)) for a, b in right)))
        assert intersection_duration(union_intervals(ranges(left)), union_intervals(ranges(right))) == expected
