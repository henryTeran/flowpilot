"""Opt-in real PostgreSQL races; each test owns a disposable random schema."""
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.database.base import Base
from app.modules.dev.routes import init_demo_data
from app.modules.institutes.models import Institute
from app.modules.employees.models import Employee
from app.modules.services.models import Service
from app.modules.appointments.models import Appointment
from app.modules.appointments.schemas import AppointmentCreate
from app.modules.appointments.service import create_appointment
from app.modules.planning.models import ServiceSession
from app.modules.planning.service import start_service_session, extend_service_session
from app.modules.tickets.models import QueueTicket
from app.modules.tickets.schemas import TicketCreate
from app.modules.tickets.service import assign_ticket, create_queue_ticket
from app.shared.time import utcnow


@pytest.fixture
def postgres_flow():
    url = os.environ.get("FLOWPILOT_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("FLOWPILOT_TEST_POSTGRES_URL required for actual PostgreSQL races")
    admin = create_engine(url)
    if admin.dialect.name != "postgresql":
        pytest.fail("PostgreSQL required; SQLite cannot validate row locks")
    schema = "fp_test_" + uuid4().hex
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            init_demo_data(db)
            institute = db.scalar(select(Institute.id))
            employee = db.scalar(select(Employee.id).where(Employee.institute_id == institute))
            service = db.scalar(select(Service.id))
            db.get(Employee, employee).status = "available"
            db.commit()
        yield engine, institute, employee, service
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def race(engine, actions):
    barrier = Barrier(len(actions))
    def execute(action):
        with Session(engine) as db:
            barrier.wait(timeout=10)
            try:
                result = action(db)
                return ("ok", result.id)
            except HTTPException as error:
                db.rollback()
                return ("conflict", error.status_code)
    with ThreadPoolExecutor(max_workers=len(actions)) as pool:
        return list(pool.map(execute, actions))


def tickets(flow, count=2):
    engine, institute, employee, service = flow
    with Session(engine) as db:
        return [create_queue_ticket(db, TicketCreate(institute_id=institute, service_id=service)).id
                for _ in range(count)]


def test_two_tickets_cannot_reserve_one_employee(postgres_flow):
    engine, institute, employee, service = postgres_flow
    first, second = tickets(postgres_flow)
    results = race(engine, [lambda db: assign_ticket(db, first, employee),
                            lambda db: assign_ticket(db, second, employee)])
    assert sorted(status for status, _ in results) == ["conflict", "ok"]
    with Session(engine) as db:
        assert len(db.scalars(select(QueueTicket).where(
            QueueTicket.institute_id == institute, QueueTicket.status == "assigned",
        )).all()) == 1


def test_two_tickets_cannot_start_on_one_employee(postgres_flow):
    engine, institute, employee, service = postgres_flow
    first, second = tickets(postgres_flow)
    results = race(engine, [lambda db: start_service_session(db, first, employee, service),
                            lambda db: start_service_session(db, second, employee, service)])
    assert sorted(status for status, _ in results) == ["conflict", "ok"]
    with Session(engine) as db:
        assert len(db.scalars(select(ServiceSession)).all()) == 1


def test_overlapping_appointment_creation_is_serialized(postgres_flow):
    engine, institute, employee, service = postgres_flow
    payload = AppointmentCreate(institute_id=institute, employee_id=employee, service_id=service,
                                customer_name="Test", start_time=utcnow() + timedelta(hours=1))
    results = race(engine, [lambda db: create_appointment(db, payload),
                            lambda db: create_appointment(db, payload)])
    assert sorted(status for status, _ in results) == ["conflict", "ok"]
    with Session(engine) as db:
        assert len(db.scalars(select(Appointment)).all()) == 1


def test_extension_and_booking_cannot_both_create_overlap(postgres_flow):
    engine, institute, employee, service = postgres_flow
    ticket = tickets(postgres_flow, 1)[0]
    with Session(engine) as db:
        session = start_service_session(db, ticket, employee, service)
        session_id, old_end = session.id, session.planned_end_time
    payload = AppointmentCreate(institute_id=institute, employee_id=employee, service_id=service,
                                customer_name="Test", start_time=old_end + timedelta(minutes=5))
    results = race(engine, [lambda db: extend_service_session(db, session_id, 10),
                            lambda db: create_appointment(db, payload)])
    assert sorted(status for status, _ in results) == ["conflict", "ok"]


def test_concurrent_creation_replay_returns_one_ticket(postgres_flow):
    engine, institute, employee, service = postgres_flow
    payload = TicketCreate(institute_id=institute, service_id=service, idempotency_key="same-arrival")
    results = race(engine, [lambda db: create_queue_ticket(db, payload),
                            lambda db: create_queue_ticket(db, payload)])
    assert results[0] == results[1]
    assert results[0][0] == "ok"
    with Session(engine) as db:
        assert len(db.scalars(select(QueueTicket)).all()) == 1


def test_assignment_and_booking_share_the_same_capacity_lock(postgres_flow):
    engine, institute, employee, service = postgres_flow
    ticket = tickets(postgres_flow, 1)[0]
    payload = AppointmentCreate(institute_id=institute, employee_id=employee, service_id=service,
                                customer_name="Test", start_time=utcnow() + timedelta(minutes=1))
    results = race(engine, [lambda db: assign_ticket(db, ticket, employee),
                            lambda db: create_appointment(db, payload)])
    assert sorted(status for status, _ in results) == ["conflict", "ok"]
