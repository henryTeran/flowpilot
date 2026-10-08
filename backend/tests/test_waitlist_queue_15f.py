from datetime import timedelta
import pytest
from sqlalchemy import select, func
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.waitlist import sources
from app.modules.employees.models import Employee
from app.modules.tickets.models import QueueTicket, TicketLine
from app.modules.resources.models import ResourceReservation
from app.modules.resources.models import ResourceRequirement
from app.modules.services.models import Service
from test_waitlist_sources_15d import prepare_sources, read
from test_waitlist_matching_15a import NOW
from test_workforce_absences_11b import setup
from test_postgres_scheduling_4d import postgres_flow


def exercise(engine, institute, employee, service, monkeypatch):
    root, event = prepare_sources(engine, institute, employee, service, monkeypatch)
    with Session(engine) as db:
        db.add(Employee(id="queue-other", institute_id=institute, first_name="Other", skills=["waitlist-care"], status="available"))
        db.flush()
        db.add(QueueTicket(id="prior-queue", institute_id=institute, ticket_number="Q", status="assigned",
            assigned_employee_id="queue-other", arrival_time=NOW-timedelta(minutes=5)))
        db.flush()
        db.add(TicketLine(id="prior-line", ticket_id="prior-queue", service_id=service, quantity=1, duration_minutes=90))
        db.commit()
        result = read(db, institute, root, event)
        # Other employee consumes the shared room virtually; the selected employee
        # is free, yet cannot reuse that room before the actual core allocation ends.
        assert result.review.options[0].employee_id == employee
        assert result.review.options[0].start == NOW+timedelta(minutes=90)
        assert result.evidence.waiting_tickets == 1 and result.evidence.unprojectable_queue_tickets == 0
        slot = result.evidence.queue_slots[0]
        assert slot.employee_id == "queue-other" and slot.resource_ids == ("waitlist-room",)
        assert slot.start == NOW and slot.end == NOW+timedelta(minutes=90)
        assert db.scalar(select(func.count()).select_from(ResourceReservation)) == 0
        db.get(QueueTicket, "prior-queue").assigned_employee_id = employee; db.commit()
        result = read(db, institute, root, event)
        assert result.review.capture.employees[[row.employee_id for row in result.review.capture.employees].index(employee)].windows[0].start == NOW+timedelta(minutes=90)
        assert result.review.options[0].start == NOW+timedelta(minutes=90)
        db.get(TicketLine, "prior-line").quantity = 2; db.commit()
        assert not read(db, institute, root, event).review.options  # three hours of existing queue work
        db.get(TicketLine, "prior-line").quantity = 1
        db.get(Employee, employee).skills = []; db.commit()
        result = read(db, institute, root, event)
        assert result.evidence.unprojectable_queue_tickets == 1
        assert result.review.unavailable_reason == "queue_projection_unknown"
        db.get(Employee, employee).skills = ["waitlist-care"]
        db.get(QueueTicket, "prior-queue").status = "cancelled"; db.commit()
        result = read(db, institute, root, event)
        assert result.evidence.waiting_tickets == 0 and result.review.options[0].start == NOW+timedelta(hours=1)
        assert db.scalar(select(func.count()).select_from(ResourceReservation)) == 0


def test_sqlite_queue_virtual_joint_capacity(client, monkeypatch):
    institute, employee, service, _, _ = setup(client)
    exercise(main_module.engine, institute, employee, service, monkeypatch)


def test_actual_postgres_queue_virtual_joint_capacity(postgres_flow, monkeypatch):
    exercise(*postgres_flow, monkeypatch)


def test_missing_machine_configuration_is_unknown_not_double_counted(client, monkeypatch):
    institute, employee, service, _, _ = setup(client)
    root, event = prepare_sources(main_module.engine, institute, employee, service, monkeypatch)
    with Session(main_module.engine) as db:
        db.get(Service, service).requires_machine = True
        db.delete(db.get(ResourceRequirement, "waitlist-need"))
        db.add(QueueTicket(id="unconfigured-queue", institute_id=institute, ticket_number="Q", status="waiting", arrival_time=NOW))
        db.flush()
        db.add(TicketLine(id="unconfigured-line", ticket_id="unconfigured-queue", service_id=service, quantity=1, duration_minutes=30))
        db.commit()
        result = read(db, institute, root, event)
        assert result.evidence.waiting_tickets == result.evidence.unprojectable_queue_tickets == 1
        assert result.evidence.queue_slots == () and result.review.capture.queue_capacity == "unknown"
        assert not result.review.options
