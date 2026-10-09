from datetime import timedelta
import pytest
from fastapi import HTTPException
from sqlalchemy import event, select
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.appointments import service as appointments
from app.modules.appointments.schemas import AppointmentCreate
from app.modules.appointments.models import Appointment, BookingEvent
from app.modules.resources.models import Resource, ResourceRequirement, ResourceReservation
from app.modules.services.models import Service
from app.shared.time import utcnow, explicit_utc_instant
from test_postgres_scheduling_4d import postgres_flow
from test_ticket_workflow import _bootstrap_reference_data


def exercise(engine, institute, employee, service):
    now = utcnow()
    payload = AppointmentCreate(institute_id=institute, employee_id=employee, service_id=service,
        customer_name="Reviewed customer", start_time=now+timedelta(hours=3), idempotency_key="preview-creation")
    with Session(engine) as db:
        db.get(Service, service).requires_machine = False
        db.add(Resource(id="preview-room", institute_id=institute, name="Preview room", kind="room", capabilities=[], status="active"))
        db.add(ResourceRequirement(id="preview-need", institute_id=institute, service_id=service, kind="room", capability="", quantity=1))
        db.commit()
        statements = []
        def collect(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement.lstrip().split()[0].upper())
        event.listen(engine, "before_cursor_execute", collect)
        try:
            preview = appointments.preview_creation(db, payload)
            assert preview.start == payload.start_time and preview.end > preview.start
            assert preview.resource_ids == ("preview-room",)
        finally:
            event.remove(engine, "before_cursor_execute", collect)
        assert not set(statements) & {"INSERT", "UPDATE", "DELETE", "ALTER", "CREATE", "DROP"}
        assert not db.scalars(select(Appointment)).all()
        assert not db.scalars(select(ResourceReservation)).all()
        assert not db.scalars(select(BookingEvent)).all()
        db.get(Resource, "preview-room").status = "maintenance"
        db.commit()
        with pytest.raises(HTTPException):
            appointments.preview_creation(db, payload)
        db.rollback()
        db.get(Resource, "preview-room").status = "active"
        db.commit()
        booked = appointments.create_appointment(db, payload)
        assert explicit_utc_instant(booked.start_time) == preview.start
        assert explicit_utc_instant(booked.end_time) == preview.end
        assert db.scalar(select(ResourceReservation)).resource_id == preview.resource_ids[0]
        with pytest.raises(HTTPException):
            appointments.preview_creation(db, payload)  # fresh check, never an idempotency receipt
        db.rollback()
        assert appointments.create_appointment(db, payload).id == booked.id  # replay still precedes current conflict checks
        assert len(db.scalars(select(Appointment)).all()) == len(db.scalars(select(BookingEvent)).all()) == 1
        with pytest.raises(HTTPException):
            appointments.preview_creation(db, payload.model_copy(update={"employee_id": "missing"}))
        db.rollback()


def test_sqlite_preview_uses_creation_and_resource_rules_without_writes(client):
    institute, employees, services = _bootstrap_reference_data(client)
    exercise(main_module.engine, institute, employees[0]["id"], services[0]["id"])


def test_postgres_preview_uses_creation_and_resource_rules_without_writes(postgres_flow):
    exercise(*postgres_flow)
