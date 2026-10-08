from datetime import datetime, timedelta, timezone
import pytest
from zoneinfo import ZoneInfo

from app.modules.waitlist.domain import Capture, Demand, match

NOW = datetime(2026, 10, 8, 10, tzinfo=timezone.utc)


def facts():
    window = dict(start=NOW, end=NOW + timedelta(hours=2))
    demand = Demand.model_validate(dict(institute_id="i", customer_id="c", service_id="s",
        declared_at=NOW-timedelta(days=1), duration_minutes=30,
        availability=[window], allowed_employee_ids=[], constraints_review="confirmed",
        availability_evidence="Cliente disponible selon déclaration", constraints_evidence="Contraintes relues avec la cliente"))
    capture = Capture.model_validate(dict(institute_id="i", captured_at=NOW,
        service=dict(service_id="s", duration_minutes=30, required_skills=["care"],
            needs=[dict(kind="room", capability="care", quantity=1)], resource_configuration="known"),
        employees=[dict(employee_id="e", skills=["care"], state="known", windows=[window])],
        resources=[dict(resource_id="r", kind="room", capabilities=["care"], state="active_known",
            reservations=[dict(start=NOW, end=NOW+timedelta(minutes=45))])],
        customer=dict(customer_id="c", history="unknown", history_reference=None, history_at=None,
            permission="unknown", channel="email", permission_at=None, permission_reference=None)))
    return demand, capture


def changed(model, **changes):
    return type(model).model_validate({**model.model_dump(), **changes})


def test_joint_interval_uses_sovereign_allocator_and_exact_boundary():
    demand, capture = facts()
    review = match(demand, capture)
    assert review.options[0].start == NOW+timedelta(minutes=45)
    assert review.options[0].end == NOW+timedelta(minutes=75)
    assert review.options[0].resource_ids == ("r",)
    assert review.action == "manual_review_only" and review.unavailable_reason is None
    # End at an occupied resource boundary is permitted; crossing it is not.
    resource = changed(capture.resources[0], reservations=[dict(start=NOW+timedelta(minutes=30), end=NOW+timedelta(hours=2))])
    result = match(demand, changed(capture, resources=[resource]))
    assert result.options[0].start == NOW and result.options[0].end == NOW+timedelta(minutes=30)
    short = changed(demand, availability=[dict(start=NOW, end=NOW+timedelta(minutes=29, seconds=59, microseconds=999999))])
    assert not match(short, changed(capture, resources=[resource])).options


def test_actual_customer_window_not_earlier_employee_or_resource_start():
    demand, capture = facts()
    demand = changed(demand, availability=[dict(start=NOW+timedelta(minutes=60), end=NOW+timedelta(minutes=90))])
    assert match(demand, capture).options[0].start == NOW+timedelta(minutes=60)
    employee = changed(capture.employees[0], windows=[dict(start=NOW+timedelta(minutes=61), end=NOW+timedelta(hours=2))])
    assert match(demand, changed(capture, employees=[employee])).unavailable_reason == "no_matching_recorded_capacity"


@pytest.mark.parametrize("field,value,reason", [
    ("constraints_review", "unknown", "constraints_unknown"),
    ("duration_minutes", 31, "duration_changed"),
])
def test_unvalidated_demand_never_becomes_eligible(field, value, reason):
    demand, capture = facts()
    changes = {field: value}
    if field == "constraints_review":
        changes["constraints_evidence"] = None
    result = match(changed(demand, **changes), capture)
    assert not result.options and result.unavailable_reason == reason


def test_skills_employee_restriction_unknown_capacity_and_resource_uncertainty():
    demand, capture = facts()
    assert not match(changed(demand, allowed_employee_ids=["other"]), capture).options
    assert not match(demand, changed(capture, employees=[changed(capture.employees[0], skills=[])])).options
    assert not match(demand, changed(capture, employees=[changed(capture.employees[0], state="unknown", windows=[])])).options
    for state in ("inactive", "unknown"):
        assert not match(demand, changed(capture, resources=[changed(capture.resources[0], state=state)])).options
    result = match(demand, changed(capture, service=changed(capture.service, resource_configuration="unknown")))
    assert result.unavailable_reason == "resource_configuration_unknown"


def test_resource_units_distinct_and_input_order_does_not_rank_customers():
    demand, capture = facts()
    needs = [dict(kind="room", capability="care", quantity=2)]
    capture = changed(capture, service=changed(capture.service, needs=needs))
    assert not match(demand, capture).options
    second = changed(capture.resources[0], resource_id="r2", reservations=[])
    employee = changed(capture.employees[0], employee_id="a")
    capture = changed(capture, resources=[second, capture.resources[0]], employees=[capture.employees[0], employee])
    expected = match(demand, capture)
    actual = match(demand, changed(capture, resources=list(reversed(capture.resources)), employees=list(reversed(capture.employees))))
    assert actual.options == expected.options
    assert actual.unavailable_reason == expected.unavailable_reason
    assert [row.employee_id for row in actual.options] == ["a", "e"]
    assert actual.options[0].resource_ids == ("r", "r2")


def test_permission_and_history_remain_context_not_dispatch_or_value():
    demand, capture = facts()
    base = match(demand, capture)
    for permission in ("granted", "refused"):
        customer = changed(capture.customer, permission=permission, permission_at=NOW,
            permission_reference="original", history="observed", history_at=NOW-timedelta(days=10), history_reference="ticket")
        review = match(demand, changed(capture, customer=customer))
        assert review.options == base.options
        assert review.capture.customer.permission == permission
        assert review.action == "manual_review_only"
    with pytest.raises(ValueError):
        changed(capture, customer=changed(capture.customer, permission="granted", permission_at=NOW+timedelta(microseconds=1), permission_reference="future"))


def test_scope_duplicate_sources_and_unsafe_copied_models_refused():
    demand, capture = facts()
    for corrupt in (changed(capture, institute_id="foreign"),
            changed(capture, service=changed(capture.service, service_id="foreign")),
            changed(capture, customer=changed(capture.customer, customer_id="foreign"))):
        with pytest.raises(ValueError):
            match(demand, corrupt)
    with pytest.raises(ValueError):
        changed(capture, employees=[capture.employees[0], capture.employees[0]])
    with pytest.raises(ValueError):
        changed(capture, resources=[capture.resources[0], capture.resources[0]])
    for corrupt in (demand.model_copy(update={"duration_minutes": True}),
            demand.model_copy(update={"declared_at": NOW.replace(tzinfo=None)})):
        with pytest.raises(ValueError):
            match(corrupt, capture)


def test_expired_windows_and_microsecond_capture_clip():
    demand, capture = facts()
    demand = changed(demand, availability=[dict(start=NOW-timedelta(hours=1), end=NOW+timedelta(minutes=30))])
    capture = changed(capture, resources=[] , service=changed(capture.service, needs=[]))
    assert match(demand, capture).options[0].start == NOW
    later = changed(capture, captured_at=NOW+timedelta(microseconds=1))
    assert not match(demand, later).options


def test_aware_sorted_non_overlapping_windows_and_explicit_evidence():
    demand, capture = facts()
    invalid = [
        dict(availability=[dict(start=NOW, end=NOW)]),
        dict(availability=[dict(start=NOW, end=NOW.replace(tzinfo=None)+timedelta(hours=1))]),
        dict(availability=[dict(start=NOW, end=NOW+timedelta(hours=1))]*2),
        dict(allowed_employee_ids=["e", "e"]),
        dict(constraints_evidence=None),
    ]
    for changes in invalid:
        with pytest.raises(ValueError):
            changed(demand, **changes)


def test_repeated_civil_hour_uses_elapsed_instants_not_wall_clock_order():
    demand, capture = facts()
    zone = ZoneInfo("Europe/Zurich")
    # 02:45 first occurrence precedes 02:15 second occurrence by30 elapsed minutes.
    start = datetime(2026, 10, 25, 2, 45, tzinfo=zone, fold=0)
    end = datetime(2026, 10, 25, 2, 15, tzinfo=zone, fold=1)
    demand = changed(demand, availability=[dict(start=start, end=end)])
    employee = changed(capture.employees[0], windows=[dict(start=start, end=end)])
    capture = changed(capture, captured_at=start, employees=[employee], resources=[],
        service=changed(capture.service, needs=[]))
    option = match(demand, capture).options[0]
    assert option.end-option.start == timedelta(minutes=30)
    assert option.start == datetime(2026, 10, 25, 0, 45, tzinfo=timezone.utc)
