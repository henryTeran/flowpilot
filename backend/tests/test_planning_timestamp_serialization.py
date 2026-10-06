from datetime import datetime, timedelta, timezone
import pytest
from app.modules.planning.schemas import ServiceSessionRead


@pytest.mark.parametrize("offset", [None, timezone.utc, timezone(timedelta(hours=2))])
def test_session_response_identifies_instants_independently_of_browser_timezone(offset):
    start = datetime(2026, 10, 6, 3, 30, tzinfo=offset)
    response = ServiceSessionRead(id="session", ticket_line_id=None, institute_id="inst",
        employee_id="staff", service_id="care", start_time=start,
        planned_end_time=start + timedelta(minutes=10), real_end_time=start + timedelta(minutes=5),
        duration_minutes=10, status="finished").model_dump(mode="json")
    for key, minutes in (("start_time", 0), ("planned_end_time", 10), ("real_end_time", 5)):
        instant = datetime.fromisoformat(response[key].replace("Z", "+00:00"))
        assert instant.tzinfo is not None
        expected = start.replace(tzinfo=timezone.utc) if offset is None else start
        assert instant == expected + timedelta(minutes=minutes)


def test_unfinished_session_response_preserves_absent_real_end():
    start = datetime(2026, 10, 6, 3, 30)
    response = ServiceSessionRead(id="session", ticket_line_id=None, institute_id="inst",
        employee_id="staff", service_id="care", start_time=start,
        planned_end_time=start + timedelta(minutes=10), real_end_time=None,
        duration_minutes=10, status="in_progress").model_dump(mode="json")
    assert response["real_end_time"] is None
