from datetime import datetime, timedelta, timezone
import pytest
from app.modules.appointments.schemas import AppointmentRead


@pytest.mark.parametrize("offset", [None, timezone.utc, timezone(timedelta(hours=2))])
def test_booking_response_preserves_booked_and_actual_instants(offset):
    start = datetime(2026, 10, 6, 3, 30, tzinfo=offset)
    dates = dict(start_time=start, end_time=start + timedelta(minutes=50),
        booked_start_time=start, booked_end_time=start + timedelta(minutes=50),
        actual_start_time=start + timedelta(minutes=5), actual_end_time=start + timedelta(minutes=55))
    response = AppointmentRead(id="booking", institute_id="inst", service_id="care", employee_id="staff",
        customer_name="Test", phone=None, notes=None, status="completed", **dates).model_dump(mode="json")
    for key, value in dates.items():
        instant = datetime.fromisoformat(response[key].replace("Z", "+00:00"))
        assert instant.tzinfo is not None
        assert instant == (value.replace(tzinfo=timezone.utc) if offset is None else value)


def test_scheduled_booking_does_not_invent_actual_or_historical_instants():
    start = datetime(2026, 10, 6, 3, 30)
    response = AppointmentRead(id="booking", institute_id="inst", service_id="care", employee_id="staff",
        customer_name="Test", phone=None, notes=None, status="scheduled",
        start_time=start, end_time=start + timedelta(minutes=50)).model_dump(mode="json")
    for key in ("booked_start_time", "booked_end_time", "actual_start_time", "actual_end_time"):
        assert response[key] is None


def test_offset_booking_is_stored_and_returned_as_the_original_instant(client):
    from sqlalchemy.orm import Session
    import app.main as main_module
    from app.modules.appointments.models import Appointment
    from app.shared.time import utcnow
    from test_ticket_workflow import _bootstrap_reference_data, _auth_headers
    institute, employees, services = _bootstrap_reference_data(client)
    original = (utcnow() + timedelta(hours=1)).astimezone(timezone(timedelta(hours=2)))
    response = client.post("/api/v1/appointments", headers=_auth_headers(institute_id=institute), json={
        "institute_id": institute, "employee_id": employees[0]["id"], "service_id": services[0]["id"],
        "customer_name": "Offset test", "start_time": original.isoformat(), "idempotency_key": "offset-booking",
    })
    assert response.status_code == 200
    receipt = response.json()
    assert datetime.fromisoformat(receipt["start_time"].replace("Z", "+00:00")) == original
    with Session(main_module.engine) as db:
        stored = db.get(Appointment, receipt["id"])
        assert stored.start_time == original.astimezone(timezone.utc).replace(tzinfo=None)
