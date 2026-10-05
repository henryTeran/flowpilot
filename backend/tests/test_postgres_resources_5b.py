from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.appointments.schemas import AppointmentCreate
from app.modules.appointments.service import create_appointment
from app.modules.employees.models import Employee
from app.modules.resources.models import Resource, ResourceRequirement, ResourceReservation
from app.shared.time import utcnow
from test_postgres_scheduling_4d import postgres_flow, race


def test_two_employees_cannot_book_one_resource_concurrently(postgres_flow):
    engine, institute, employee, service = postgres_flow
    with Session(engine) as db:
        other = db.scalar(select(Employee).where(Employee.institute_id == institute, Employee.id != employee))
        other.status = "available"
        other_id = other.id
        db.add(Resource(id="shared-room", institute_id=institute, name="Shared", kind="room", capabilities=[], status="active"))
        db.add(ResourceRequirement(id="room-need", institute_id=institute, service_id=service, kind="room", capability="", quantity=1))
        db.commit()
    start = utcnow() + timedelta(hours=1)
    payloads = [AppointmentCreate(institute_id=institute, employee_id=employee_id, service_id=service,
                                  customer_name="Test", start_time=start) for employee_id in (employee, other_id)]
    results = race(engine, [lambda db: create_appointment(db, payloads[0]), lambda db: create_appointment(db, payloads[1])])
    assert sorted(status for status, _ in results) == ["conflict", "ok"]
    with Session(engine) as db:
        assert len(db.scalars(select(ResourceReservation)).all()) == 1
