"""Owned historical activity and conflicting legacy reservations; no clock patch.

Conflicts are intentionally imported snapshots, not bookings accepted by the
current allocator. This fixture has no production API or mutation endpoint.
"""
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.modules.appointments.models import Appointment
from app.modules.resources.models import ResourceReservation


def seed_planning(engine, institute):
    activity_day = "2025-10-26"
    conflict_day = "2027-11-14"
    with Session(engine) as db:
        for index, (first, last) in enumerate(((15, 45), (30, 60), (180, 195))):
            start = datetime(2025, 10, 26, tzinfo=timezone.utc)+timedelta(minutes=first)
            end = datetime(2025, 10, 26, tzinfo=timezone.utc)+timedelta(minutes=last)
            db.add(Appointment(id=f"browser-activity-{index}", institute_id=institute,
                employee_id="emp-angela", service_id="svc-aisselles", customer_name="Legacy activity",
                start_time=start, end_time=end, actual_start_time=start, actual_end_time=end, status="completed"))
        for index, (first, last) in enumerate(((0, 60), (30, 90), (90, 100))):
            start = datetime(2027, 11, 14, 9, tzinfo=timezone.utc)+timedelta(minutes=first)
            end = datetime(2027, 11, 14, 9, tzinfo=timezone.utc)+timedelta(minutes=last)
            db.add(Appointment(id=f"browser-conflict-{index}", institute_id=institute,
                employee_id="emp-angela", service_id="svc-soin-profond", customer_name="Legacy conflict",
                start_time=start, end_time=end, status="scheduled"))
        db.flush()
        for index, (first, last) in enumerate(((0, 60), (30, 90), (90, 100))):
            db.add(ResourceReservation(id=f"browser-reservation-{index}", institute_id=institute,
                resource_id="browser-room", appointment_id=f"browser-conflict-{index}",
                start_time=datetime(2027, 11, 14, 9, tzinfo=timezone.utc)+timedelta(minutes=first),
                end_time=datetime(2027, 11, 14, 9, tzinfo=timezone.utc)+timedelta(minutes=last), status="reserved"))
        db.commit()
    return dict(activity_day=activity_day, conflict_day=conflict_day, employee_id="emp-angela", resource_id="browser-room")


def read_snapshot(engine):
    with Session(engine) as db:
        return {model.__tablename__: [dict(id=row.id, status=row.status, start=str(row.start_time),
            end=str(row.end_time), **(dict(actual_start=str(row.actual_start_time), actual_end=str(row.actual_end_time))
            if model is Appointment else {})) for row in db.scalars(select(model).where(model.id.like("browser-%")).order_by(model.id))]
            for model in (Appointment, ResourceReservation)}
