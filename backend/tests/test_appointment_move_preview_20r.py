from datetime import datetime, timedelta
import pytest
from fastapi import HTTPException
from sqlalchemy import event, select
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.appointments import service as appointments
from app.modules.appointments.schemas import AppointmentCreate, AppointmentUpdate
from app.modules.appointments.events import snapshot
from app.modules.appointments.models import Appointment, BookingEvent
from app.modules.resources.models import Resource, ResourceRequirement, ResourceReservation
from app.modules.services.models import Service
from app.shared.time import utcnow, explicit_utc_instant
from test_postgres_scheduling_4d import postgres_flow
from test_ticket_workflow import _bootstrap_reference_data


def instants(value):
    return {key: datetime.fromisoformat(item) if item is not None and key.endswith("_time") else item
            for key, item in value.items()}


def exercise(engine, institute, employee, service):
    now = utcnow()
    with Session(engine) as db:
        db.get(Service, service).requires_machine = False
        db.add(Resource(id="move-room", institute_id=institute, name="Move room", kind="room", capabilities=[], status="active"))
        db.add(ResourceRequirement(id="move-need", institute_id=institute, service_id=service, kind="room", capability="", quantity=1))
        db.commit()
        booked = appointments.create_appointment(db, AppointmentCreate(institute_id=institute, employee_id=employee,
            service_id=service, customer_name="Retained customer", start_time=now+timedelta(hours=2)))
        identifier = booked.id
        original = snapshot(booked)
        # A partially overlapping proposed interval must exclude its own booking/reservation.
        proposal = AppointmentUpdate(start_time=explicit_utc_instant(booked.start_time)+timedelta(minutes=1))
        statements = []
        def collect(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement.lstrip().split()[0].upper())
        event.listen(engine, "before_cursor_execute", collect)
        try:
            preview = appointments.preview_update(db, institute, identifier, proposal)
            assert preview.changed_slot and preview.resource_ids == ("move-room",)
            assert preview.before == original
            assert snapshot(booked) == original
        finally:
            event.remove(engine, "before_cursor_execute", collect)
        assert not set(statements) & {"INSERT", "UPDATE", "DELETE", "ALTER", "CREATE", "DROP"}
        assert len(db.scalars(select(BookingEvent)).all()) == 1
        moved = appointments.update_appointment(db, identifier, proposal, "reviewer", commit=False)
        assert instants(snapshot(moved)) == instants(preview.after)
        reservation = db.scalar(select(ResourceReservation).where(ResourceReservation.appointment_id == identifier))
        assert explicit_utc_instant(reservation.start_time) == proposal.start_time
        db.rollback()
        assert snapshot(db.get(Appointment, identifier)) == original
        assert len(db.scalars(select(BookingEvent)).all()) == 1
        reservation = db.scalar(select(ResourceReservation).where(ResourceReservation.appointment_id == identifier))
        assert explicit_utc_instant(reservation.start_time) == datetime.fromisoformat(original["start_time"])
        appointments.update_appointment(db, identifier, proposal, "reviewer")
        assert instants(snapshot(db.get(Appointment, identifier))) == instants(preview.after)
        with pytest.raises(HTTPException):
            appointments.preview_update(db, "foreign", identifier, proposal)
        db.rollback()
        no_op = appointments.preview_update(db, institute, identifier, proposal)
        assert not no_op.changed_slot and no_op.before == no_op.after
        db.rollback()
        db.get(Resource, "move-room").status = "maintenance"
        db.commit()
        with pytest.raises(HTTPException):
            appointments.preview_update(db, institute, identifier, AppointmentUpdate(start_time=now+timedelta(hours=4)))
        db.rollback()
        assert instants(snapshot(db.get(Appointment, identifier))) == instants(preview.after)


def test_sqlite_owned_move_preview_and_caller_transaction(client):
    institute, employees, services = _bootstrap_reference_data(client)
    exercise(main_module.engine, institute, employees[0]["id"], services[0]["id"])


def test_postgres_owned_move_preview_and_caller_transaction(postgres_flow):
    exercise(*postgres_flow)
