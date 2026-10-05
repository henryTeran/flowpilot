from datetime import datetime, timedelta, timezone

from app.modules.resources.allocation_domain import ResourceNeed, ResourceTimeline
from app.modules.scheduling.waiting_domain import EmployeeTimeline, QueueWork, project_queue

NOW = datetime(2026, 10, 5, 10, tzinfo=timezone.utc)


def at(minutes):
    return NOW + timedelta(minutes=minutes)


def work(identifier, **kwargs):
    return QueueWork(identifier, 20, resource_needs=(ResourceNeed("room"),), **kwargs)


def test_shared_room_serializes_parallel_employee_projections():
    results = project_queue([EmployeeTimeline("a", NOW), EmployeeTimeline("b", NOW)],
                            [work("one"), work("two")], (ResourceTimeline("room", "room"),))
    assert results["one"].estimated_start_time == NOW
    assert results["two"].estimated_start_time == at(20)


def test_joint_search_rechecks_employee_after_resource_window_moves():
    results = project_queue([EmployeeTimeline("a", NOW, ((at(15), at(40)),))], [work("one")],
                            (ResourceTimeline("room", "room", reservations=((NOW, at(10)),)),))
    assert results["one"].estimated_start_time == at(40)


def test_missing_or_unknown_resources_never_invent_estimates():
    employee = [EmployeeTimeline("a", NOW)]
    assert project_queue(employee, [work("one")])["one"].estimated_start_time is None
    assert project_queue(employee, [work("one")], (ResourceTimeline("room", "room", capacity_known=False),))["one"].estimated_start_time is None


def test_assigned_owner_does_not_block_itself_or_free_competing_capacity():
    resources = (ResourceTimeline("room", "room", reservations=((NOW, at(20)),)),)
    queue = [work("waiting"), work("assigned", assigned_employee_id="b",
                                   owned_reservations=(("room", NOW, at(20)),))]
    results = project_queue([EmployeeTimeline("a", NOW), EmployeeTimeline("b", NOW)], queue, resources)
    assert results["assigned"].estimated_start_time == NOW
    assert results["waiting"].estimated_start_time == at(20)


def test_failed_assigned_projection_preserves_its_resource_commitment():
    resources = (ResourceTimeline("room", "room", reservations=((NOW, at(20)),)),)
    queue = [work("assigned", assigned_employee_id="missing", owned_reservations=(("room", NOW, at(20)),)), work("waiting")]
    results = project_queue([EmployeeTimeline("a", NOW)], queue, resources)
    assert results["assigned"].estimated_start_time is None
    assert results["waiting"].estimated_start_time == at(20)
