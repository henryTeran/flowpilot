from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.appointments.schemas import AppointmentCreate, AppointmentUpdate
from app.modules.appointments.service import create_appointment, update_appointment
from app.modules.appointments.models import Appointment, BookingEvent
from app.modules.resources.models import ResourceReservation
from app.shared.time import utcnow
from test_postgres_scheduling_4d import postgres_flow, race
from test_postgres_resources_5b import shared_room


def test_competing_moves_cannot_reserve_one_room(postgres_flow):
    engine, institute, employee, service = postgres_flow
    other = shared_room(postgres_flow)
    now = utcnow()
    with Session(engine) as db:
        bookings = [create_appointment(db, AppointmentCreate(institute_id=institute, employee_id=employee_id,
            service_id=service, customer_name="Test", start_time=now + timedelta(hours=index + 1))).id
            for index, employee_id in enumerate((employee, other))]
    target = now + timedelta(hours=3)
    results = race(engine, [lambda db: update_appointment(db, bookings[0], AppointmentUpdate(start_time=target)),
                            lambda db: update_appointment(db, bookings[1], AppointmentUpdate(start_time=target))])
    assert sorted(status for status, _ in results) == ["conflict", "ok"]
    with Session(engine) as db:
        appointments = db.scalars(select(Appointment)).all()
        assert sum(appointment.start_time == target for appointment in appointments) == 1
        for appointment in appointments:
            row = db.scalar(select(ResourceReservation).where(ResourceReservation.appointment_id == appointment.id,
                                                               ResourceReservation.status != "released"))
            assert (row.start_time, row.end_time) == (appointment.start_time, appointment.end_time)


def test_duplicate_booking_requests_replay_one_resource_and_event(postgres_flow):
    engine, institute, employee, service = postgres_flow
    shared_room(postgres_flow)
    payload = AppointmentCreate(institute_id=institute, employee_id=employee, service_id=service,
        customer_name="Test", start_time=utcnow() + timedelta(hours=1), idempotency_key="same-reservation")
    results = race(engine, [lambda db: create_appointment(db, payload), lambda db: create_appointment(db, payload)])
    assert all(status == "ok" for status, _ in results)
    assert results[0][1] == results[1][1]
    with Session(engine) as db:
        assert len(db.scalars(select(Appointment)).all()) == 1
        assert len(db.scalars(select(ResourceReservation)).all()) == 1
        assert len(db.scalars(select(BookingEvent)).all()) == 1
