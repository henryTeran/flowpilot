from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

import app.main as main_module
from app.modules.appointments.models import Appointment, BookingEvent, AppointmentInvoiceLine
from app.modules.tickets.models import QueueTicket, TicketLine
from app.modules.realtime.models import PlanningRevision
from app.shared.time import utcnow
from test_ticket_workflow import _auth_headers, _bootstrap_reference_data
from test_postgres_scheduling_4d import postgres_flow, race


def test_booking_finish_replay_enters_checkout_once_and_payment_preserves_attribution(client, monkeypatch):
    institute, employees, services = _bootstrap_reference_data(client)
    employee = employees[0]["id"]
    operator = _auth_headers(institute_id=institute)
    booked = client.post("/api/v1/appointments", headers=operator, json={
        "institute_id": institute, "employee_id": employee, "service_id": services[0]["id"],
        "customer_name": "Checkout test", "start_time": (utcnow() + timedelta(minutes=1)).isoformat(),
    })
    assert booked.status_code == 200
    path = f"/api/v1/appointments/{booked.json()['id']}"
    assert client.patch(path + "/start", headers=operator).status_code == 200
    assert client.patch(path + "/complete", headers=_auth_headers(institute_id="foreign")).status_code == 403
    from app.modules.tickets import service as ticket_service
    from app.shared.exceptions import business_error
    original = ticket_service.prepare_booking_checkout
    def fail_after_checkout_flush(db, appointment, actor_id=None):
        original(db, appointment, actor_id)
        db.flush()
        raise business_error("Injected checkout failure")
    with Session(main_module.engine) as db:
        revision = db.get(PlanningRevision, institute).revision
    with monkeypatch.context() as patch:
        patch.setattr(ticket_service, "prepare_booking_checkout", fail_after_checkout_flush)
        assert client.patch(path + "/complete", headers=operator).status_code == 400
    with Session(main_module.engine) as db:
        assert db.get(Appointment, booked.json()["id"]).status == "in_progress"
        assert db.get(Appointment, booked.json()["id"]).checkout_ticket_id is None
        assert db.get(PlanningRevision, institute).revision == revision
        assert db.scalars(select(QueueTicket)).all() == []
        assert db.scalars(select(AppointmentInvoiceLine)).all() == []
    finished = client.patch(path + "/complete", headers=operator)
    assert finished.status_code == 200, finished.text
    replay = client.patch(path + "/complete", headers=operator)
    assert replay.status_code == 200 and replay.json() == finished.json()
    ticket_id = finished.json()["checkout_ticket_id"]
    waiting = client.get(f"/api/v1/tickets/waiting?institute_id={institute}", headers=operator).json()
    ticket = next(row for row in waiting if row["id"] == ticket_id)
    assert ticket["status"] == "ready_for_checkout"
    assert ticket["assigned_employee_id"] is None
    assert ticket["lines"][0]["performed_by_employee_id"] == employee
    assert ticket["lines"][0]["status"] == "completed"
    payment = {"employee_id": employees[1]["id"], "payment_method": "cb"}
    paid = client.patch(f"/api/v1/tickets/{ticket_id}/checkout/pay", headers=operator, json=payment)
    assert paid.status_code == 200, paid.text
    assert client.patch(f"/api/v1/tickets/{ticket_id}/checkout/pay", headers=operator, json=payment).json() == paid.json()
    with Session(main_module.engine) as db:
        assert len(db.scalars(select(QueueTicket)).all()) == 1
        assert len(db.scalars(select(TicketLine)).all()) == 1
        assert len(db.scalars(select(BookingEvent).where(BookingEvent.event_type == "completed")).all()) == 1
        assert db.get(Appointment, booked.json()["id"]).checkout_ticket_id == ticket_id
        assert db.get(QueueTicket, ticket_id).paid_employee_id == employees[1]["id"]
        assert db.scalar(select(TicketLine)).performed_by_employee_id == employee
        fact = db.get(AppointmentInvoiceLine, booked.json()["id"])
        assert fact.ticket_id == ticket_id and fact.actor_id == "test-user"
        assert fact.ticket_line_id == db.scalar(select(TicketLine)).id


def test_competing_booking_finishes_create_one_checkout(postgres_flow):
    from app.modules.appointments.schemas import AppointmentCreate
    from app.modules.appointments.service import create_appointment, start_appointment, complete_appointment
    engine, institute, employee, service = postgres_flow
    with Session(engine) as db:
        appointment = create_appointment(db, AppointmentCreate(institute_id=institute, employee_id=employee,
            service_id=service, customer_name="Race", start_time=utcnow() + timedelta(minutes=1)))
        identifier = appointment.id
        start_appointment(db, identifier)
    results = race(engine, [lambda db: complete_appointment(db, identifier), lambda db: complete_appointment(db, identifier)])
    assert results == [("ok", identifier), ("ok", identifier)]
    with Session(engine) as db:
        ticket = db.get(QueueTicket, db.get(Appointment, identifier).checkout_ticket_id)
        assert ticket.status == "ready_for_checkout"
        assert len(db.scalars(select(QueueTicket)).all()) == 1
        assert len(db.scalars(select(TicketLine)).all()) == 1
        facts = db.scalars(select(AppointmentInvoiceLine)).all()
        assert len(facts) == 1 and facts[0].ticket_id == ticket.id
        assert facts[0].ticket_line_id == db.scalar(select(TicketLine)).id
