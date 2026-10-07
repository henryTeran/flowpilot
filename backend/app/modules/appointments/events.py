"""Booking history without customer names, phone numbers or free-text notes."""
from datetime import datetime, timezone
from app.modules.appointments.models import BookingEvent
from app.shared.ids import new_id
from app.shared.time import utcnow


def snapshot(appointment):
    fields = ("status", "employee_id", "service_id", "customer_id", "start_time", "end_time",
              "booked_start_time", "booked_end_time", "actual_start_time", "actual_end_time", "checkout_ticket_id")
    return {key: (value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value).isoformat() if isinstance(value, datetime) else value
            for key in fields for value in [getattr(appointment, key)]}


def record_booking_event(db, appointment, event_type, before, actor_id=None):
    identifier, at = new_id("be"), utcnow()
    reference = None
    if event_type == "created" or event_type == "modified" and before and before["service_id"] != appointment.service_id:
        from app.modules.appointments.price_references import capture
        reference = capture(db, appointment, identifier, event_type, at, actor_id)
    db.add(BookingEvent(id=identifier, institute_id=appointment.institute_id,
        appointment_id=appointment.id, event_type=event_type, actor_id=actor_id,
        occurred_at=at, before=before, after=snapshot(appointment), price_reference=reference))
