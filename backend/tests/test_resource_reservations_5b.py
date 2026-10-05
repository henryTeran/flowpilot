from datetime import timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

import app.main as main_module
from app.modules.appointments.models import Appointment
from app.modules.resources.allocation_domain import ResourceNeed
from app.modules.resources.models import Resource, ResourceReservation
from app.modules.resources.reservations import reserve, release
from app.shared.time import utcnow
from test_ticket_workflow import _bootstrap_reference_data, _create_ticket


def test_reservation_replay_conflict_release_and_rollback(client):
    institute, _, services = _bootstrap_reference_data(client)
    tickets = [_create_ticket(client, institute, services[0]["id"])["id"] for _ in range(2)]
    start = utcnow() + timedelta(hours=1)
    end = start + timedelta(minutes=20)
    with Session(main_module.engine) as db:
        db.add(Resource(id="room-test", institute_id=institute, name="Test room", kind="room", capabilities=[], status="active"))
        db.commit()
        reserve(db, institute, [ResourceNeed("room")], start, end, ticket_id=tickets[0])
        db.commit()
        reserve(db, institute, [ResourceNeed("room")], start, end, ticket_id=tickets[0])
        db.commit()
        assert len(db.scalars(select(ResourceReservation)).all()) == 1
        with pytest.raises(HTTPException):
            reserve(db, institute, [ResourceNeed("room")], start, end, ticket_id=tickets[1])
        db.rollback()
        assert db.scalar(select(ResourceReservation)).ticket_id == tickets[0]
        release(db, institute, ticket_id=tickets[0])
        db.rollback()
        with pytest.raises(HTTPException):
            reserve(db, institute, [ResourceNeed("room")], start, end, ticket_id=tickets[1])
        db.rollback()
        release(db, institute, ticket_id=tickets[0])
        reserve(db, institute, [ResourceNeed("room")], start, end, ticket_id=tickets[1], in_use=True)
        db.commit()
        rows = db.scalars(select(ResourceReservation).order_by(ResourceReservation.ticket_id)).all()
        assert {row.status for row in rows} == {"released", "in_use"}


def test_overdue_occupancy_is_unknown_and_owner_is_validated(client):
    institute, _, services = _bootstrap_reference_data(client)
    tickets = [_create_ticket(client, institute, services[0]["id"])["id"] for _ in range(2)]
    now = utcnow()
    with Session(main_module.engine) as db:
        db.add(Resource(id="room-test", institute_id=institute, name="Test room", kind="room", capabilities=[], status="active"))
        db.commit()
        reserve(db, institute, [ResourceNeed("room")], now - timedelta(minutes=30), now - timedelta(minutes=10), ticket_id=tickets[0], in_use=True)
        db.commit()
        with pytest.raises(HTTPException):
            reserve(db, institute, [ResourceNeed("room")], now, now + timedelta(minutes=20), ticket_id=tickets[1])
        db.rollback()
        with pytest.raises(HTTPException) as error:
            reserve(db, institute, [], now, now + timedelta(minutes=20), ticket_id="missing")
        assert error.value.status_code == 404
        db.rollback()
        with pytest.raises(ValueError):
            reserve(db, institute, [], now, now + timedelta(minutes=20))


def test_ticket_and_appointment_owners_share_one_resource_pool(client):
    institute, employees, services = _bootstrap_reference_data(client)
    ticket = _create_ticket(client, institute, services[0]["id"])["id"]
    start = utcnow() + timedelta(hours=1)
    end = start + timedelta(minutes=20)
    with Session(main_module.engine) as db:
        db.add(Resource(id="room-test", institute_id=institute, name="Test room", kind="room", capabilities=[], status="active"))
        db.add(Appointment(id="appointment-test", institute_id=institute, employee_id=employees[0]["id"],
                           service_id=services[0]["id"], customer_name="Test", start_time=start, end_time=end, status="scheduled"))
        db.commit()
        reserve(db, institute, [ResourceNeed("room")], start, end, appointment_id="appointment-test")
        db.commit()
        with pytest.raises(HTTPException):
            reserve(db, institute, [ResourceNeed("room")], start, end, ticket_id=ticket)
        db.rollback()
        release(db, institute, appointment_id="appointment-test")
        reserve(db, institute, [ResourceNeed("room")], start, end, ticket_id=ticket)
        db.commit()
        with pytest.raises(HTTPException):
            reserve(db, institute, [ResourceNeed("room")], start, end, appointment_id="appointment-test")
        db.rollback()
