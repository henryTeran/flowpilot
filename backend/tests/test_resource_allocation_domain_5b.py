from datetime import datetime, timedelta, timezone

import pytest

from app.modules.resources.allocation_domain import (
    ResourceNeed, ResourceTimeline, match_resources, next_resource_window,
)

NOW = datetime(2026, 10, 5, 10, tzinfo=timezone.utc)


def at(minutes):
    return NOW + timedelta(minutes=minutes)


def test_specialized_and_generic_needs_do_not_greedily_steal_capacity():
    resources = [ResourceTimeline("a", "device", frozenset({"laser"})),
                 ResourceTimeline("b", "device")]
    needs = [ResourceNeed("device"), ResourceNeed("device", "laser")]
    assert match_resources(resources, needs, NOW, at(20)).resource_ids == ("a", "b")
    assert match_resources(reversed(resources), reversed(needs), NOW, at(20)).resource_ids == ("a", "b")
    assert match_resources(resources[:1], needs, NOW, at(20)) is None


def test_quantity_requires_distinct_compatible_active_known_resources():
    resources = [ResourceTimeline("a", "bed"), ResourceTimeline("b", "bed", active=False),
                 ResourceTimeline("c", "bed", capacity_known=False), ResourceTimeline("d", "chair")]
    assert match_resources(resources, [ResourceNeed("bed", quantity=2)], NOW, at(20)) is None
    assert match_resources(resources, [ResourceNeed("bed")], NOW, at(20)).resource_ids == ("a",)


def test_entire_interval_must_fit_and_touching_boundaries_are_free():
    resource = ResourceTimeline("a", "room", reservations=((at(10), at(30)), (at(30), at(40))))
    needs = [ResourceNeed("room")]
    assert match_resources([resource], needs, NOW, at(10)) is not None
    assert match_resources([resource], needs, NOW, at(11)) is None
    assert next_resource_window([resource], needs, NOW, 20).start == at(40)
    assert next_resource_window([resource], needs, NOW, 20, latest_end=at(59)) is None


def test_joint_resources_wait_until_all_requirements_fit():
    resources = [ResourceTimeline("room", "room", reservations=((NOW, at(20)),)),
                 ResourceTimeline("device", "device", reservations=((at(15), at(40)),))]
    result = next_resource_window(resources, [ResourceNeed("room"), ResourceNeed("device")], NOW, 20)
    assert result.start == at(40)
    assert result.end == at(60)


def test_stable_ties_and_no_requirement_preserve_normal_service_window():
    resources = [ResourceTimeline("z", "chair"), ResourceTimeline("a", "chair")]
    assert match_resources(resources, [ResourceNeed("chair")], NOW, at(20)).resource_ids == ("a",)
    assert next_resource_window([], [], NOW, 20).resource_ids == ()


@pytest.mark.parametrize("duration", [0, -1])
def test_invalid_duration_rejected(duration):
    with pytest.raises(ValueError):
        next_resource_window([], [], NOW, duration)


def test_invalid_identity_quantity_and_interval_rejected():
    resource = ResourceTimeline("a", "bed")
    with pytest.raises(ValueError):
        match_resources([resource, resource], [], NOW, at(20))
    with pytest.raises(ValueError):
        match_resources([resource], [ResourceNeed("bed", quantity=0)], NOW, at(20))
    with pytest.raises(ValueError):
        match_resources([], [], NOW, NOW)
