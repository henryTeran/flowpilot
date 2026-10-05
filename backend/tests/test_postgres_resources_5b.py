from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.appointments.schemas import AppointmentCreate
from app.modules.appointments.service import create_appointment
from app.modules.employees.models import Employee
from app.modules.resources.models import Resource, ResourceRequirement, ResourceReservation
from app.modules.planning.service import start_service_session, extend_service_session
from app.modules.planning.models import ServiceSession, SessionExtension
from app.modules.tickets.service import assign_ticket
from app.modules.tickets.models import QueueTicket
from app.shared.time import utcnow
from test_postgres_scheduling_4d import postgres_flow, race, tickets


def shared_room(flow):
    engine, institute, employee, service = flow
    with Session(engine) as db:
        other = db.scalar(select(Employee).where(Employee.institute_id == institute, Employee.id != employee))
        other.status = "available"
        other_id = other.id
        db.add(Resource(id="shared-room", institute_id=institute, name="Shared", kind="room", capabilities=[], status="active"))
        db.add(ResourceRequirement(id="room-need", institute_id=institute, service_id=service, kind="room", capability="", quantity=1))
        db.commit()
    return other_id


def test_two_employees_cannot_book_one_resource_concurrently(postgres_flow):
    engine, institute, employee, service = postgres_flow
    other_id = shared_room(postgres_flow)
    start = utcnow() + timedelta(hours=1)
    payloads = [AppointmentCreate(institute_id=institute, employee_id=employee_id, service_id=service,
                                  customer_name="Test", start_time=start) for employee_id in (employee, other_id)]
    results = race(engine, [lambda db: create_appointment(db, payloads[0]), lambda db: create_appointment(db, payloads[1])])
    assert sorted(status for status, _ in results) == ["conflict", "ok"]
    with Session(engine) as db:
        assert len(db.scalars(select(ResourceReservation)).all()) == 1


def test_walkin_assignment_and_other_employee_booking_share_resource_lock(postgres_flow):
    engine, institute, employee, service = postgres_flow
    other = shared_room(postgres_flow)
    ticket = tickets(postgres_flow, 1)[0]
    payload = AppointmentCreate(institute_id=institute, employee_id=other, service_id=service,
                                customer_name="Test", start_time=utcnow() + timedelta(minutes=1))
    results = race(engine, [lambda db: assign_ticket(db, ticket, employee),
                            lambda db: create_appointment(db, payload)])
    assert sorted(status for status, _ in results) == ["conflict", "ok"]
    with Session(engine) as db:
        rows = db.scalars(select(ResourceReservation)).all()
        assert len(rows) == 1
        assert (db.get(QueueTicket, ticket).status == "assigned") == (rows[0].ticket_id == ticket)


def test_resource_extension_and_other_employee_booking_cannot_both_overlap(postgres_flow):
    engine, institute, employee, service = postgres_flow
    other = shared_room(postgres_flow)
    ticket = tickets(postgres_flow, 1)[0]
    with Session(engine) as db:
        session = start_service_session(db, ticket, employee, service)
        session_id, old_end = session.id, session.planned_end_time
    payload = AppointmentCreate(institute_id=institute, employee_id=other, service_id=service,
                                customer_name="Test", start_time=old_end + timedelta(minutes=5))
    results = race(engine, [lambda db: extend_service_session(db, session_id, 10, "resource-race"),
                            lambda db: create_appointment(db, payload)])
    assert sorted(status for status, _ in results) == ["conflict", "ok"]
    with Session(engine) as db:
        session = db.get(ServiceSession, session_id)
        reservation = db.scalar(select(ResourceReservation).where(ResourceReservation.ticket_id == ticket))
        assert reservation.end_time == session.planned_end_time
        extended = session.planned_end_time == old_end + timedelta(minutes=10)
        assert len(db.scalars(select(SessionExtension)).all()) == int(extended)
