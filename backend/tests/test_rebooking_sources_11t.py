from datetime import datetime, timedelta, timezone
import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.workforce import rebooking_sources as sources
from app.modules.appointments.models import Appointment, BookingEvent
from app.modules.planning.models import ServiceSession
from app.modules.tickets.models import QueueTicket, TicketLine
from app.modules.customers.models import Customer
from test_workforce_absences_11b import setup
from test_postgres_scheduling_4d import postgres_flow


def exercise(engine, institute, employee, service):
    now = datetime(2026, 10, 7, 12, tzinfo=timezone.utc)
    first, last = now-timedelta(hours=2), now-timedelta(hours=1)
    booked = now+timedelta(days=1)
    with Session(engine) as db:
        db.add(Customer(id="rebook-customer", institute_id=institute, display_name="Private",
            search_name="private", phone_digits="", idempotency_key="customer-key", creation_fingerprint="fingerprint", created_at=first))
        db.add(QueueTicket(id="rebook-ticket", institute_id=institute, ticket_number="R1", customer_id="rebook-customer", arrival_time=first, status="paid"))
        db.flush()
        db.add(TicketLine(id="rebook-line", ticket_id="rebook-ticket", service_id=service, quantity=1, duration_minutes=60, performed_by_employee_id=employee))
        db.flush()
        session = ServiceSession(id="rebook-session", ticket_line_id="rebook-line", institute_id=institute, employee_id=employee,
            service_id=service, start_time=first, real_end_time=last, planned_end_time=now+timedelta(hours=5), duration_minutes=60, status="completed")
        original = Appointment(id="rebook-original", institute_id=institute, employee_id=employee, service_id=service,
            customer_name="Different name", customer_id="rebook-customer", start_time=first, end_time=last,
            actual_start_time=first, actual_end_time=last, status="completed")
        target = Appointment(id="rebook-target", institute_id=institute, employee_id=employee, service_id=service,
            customer_name="Private", customer_id="rebook-customer", start_time=booked, end_time=booked+timedelta(hours=1),
            booked_start_time=booked, booked_end_time=booked+timedelta(hours=1), status="scheduled")
        db.add_all([session, original, target]); db.flush()
        snapshot = {"customer_id": "rebook-customer", "status": "scheduled", "start_time": booked.isoformat(), "end_time": (booked+timedelta(hours=1)).isoformat()}
        event = BookingEvent(id="rebook-event", institute_id=institute, appointment_id=target.id, event_type="created", actor_id="reception",
            occurred_at=last+timedelta(microseconds=1), after=snapshot)
        db.add(event); db.commit()
        for kind, identifier in [("session", session.id), ("appointment", original.id)]:
            source = sources.execution(db, institute, kind, identifier, now)
            assert source.employee_id == employee and source.actual_end == last and source.customer_id == "rebook-customer"
            capture = sources.booking(db, institute, target.id, source, now)
            assert capture.creation_event_id == event.id and capture.original_start == booked
            assert capture.created_at == last+timedelta(microseconds=1)
            assert "customer_name" not in source.model_dump() and "phone" not in capture.model_dump()
        source = sources.execution(db, institute, "session", session.id, now)
        for field, bad in [("status", "cancelled"), ("customer_id", None), ("customer_id", "unregistered")]:
            old = getattr(target, field); setattr(target, field, bad); db.flush()
            with pytest.raises(HTTPException): sources.booking(db, institute, target.id, source, now)
            setattr(target, field, old); db.flush()
        for occurred in [last-timedelta(microseconds=1), now+timedelta(microseconds=1)]:
            event.occurred_at = occurred; db.flush()
            with pytest.raises(HTTPException): sources.booking(db, institute, target.id, source, now)
        event.occurred_at = last; db.flush()
        # Equal instants permit a booking created immediately on completion.
        assert sources.booking(db, institute, target.id, source, now).created_at == last
        for key, bad in [("customer_id", "another"), ("status", "completed"), ("start_time", booked.replace(tzinfo=None).isoformat()),
                         ("start_time", 42), ("end_time", booked.isoformat())]:
            event.after = {**snapshot, key: bad}; db.flush()
            with pytest.raises(HTTPException): sources.booking(db, institute, target.id, source, now)
        event.after = snapshot; db.flush()
        db.add(BookingEvent(id="ambiguous-event", institute_id=institute, appointment_id=target.id, event_type="created", occurred_at=last, after=snapshot)); db.flush()
        with pytest.raises(HTTPException): sources.booking(db, institute, target.id, source, now)
        for field, bad in [("real_end_time", None), ("real_end_time", first), ("real_end_time", now+timedelta(microseconds=1)), ("status", "in_progress")]:
            old = getattr(session, field); setattr(session, field, bad); db.flush()
            with pytest.raises(HTTPException): sources.execution(db, institute, "session", session.id, now)
            setattr(session, field, old); db.flush()
        session.ticket_line_id = None; db.flush()
        with pytest.raises(HTTPException): sources.execution(db, institute, "session", session.id, now)
        with pytest.raises(HTTPException): sources.execution(db, "foreign", "appointment", original.id, now)
        with pytest.raises(HTTPException): sources.execution(db, institute, "ticket", session.id, now)
        with pytest.raises(HTTPException): sources.booking(db, institute, original.id, sources.execution(db, institute, "appointment", original.id, now), now)


def test_sqlite_rebooking_source_capture(client):
    institute, employee, service, _, _ = setup(client)
    exercise(main_module.engine, institute, employee, service)


def test_actual_postgres_rebooking_source_capture(postgres_flow):
    exercise(*postgres_flow)
