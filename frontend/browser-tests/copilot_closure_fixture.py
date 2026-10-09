"""Historical native closure operations in the owned new browser database.

Only fixture seeding patches event clocks; every patch ends before HTTP serving.
No payment adapter, live clock override or public mutation endpoint exists.
"""
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.modules.appointments import service as bookings, events as booking_events
from app.modules.appointments.models import Appointment, BookingEvent
from app.modules.tickets import service as tickets, events as ticket_events
from app.modules.tickets.models import QueueTicket, QueueEvent


def seed_closures(engine, institute):
    at = datetime(2025, 10, 26, 1, tzinfo=timezone.utc)
    with ExitStack() as patches, Session(engine) as db:
        for module in (bookings, booking_events, tickets, ticket_events):
            patches.enter_context(patch.object(module, "utcnow", lambda: at))
        for index in range(25):
            start = at-timedelta(days=1)+timedelta(minutes=index*30)
            db.add(Appointment(id=f"browser-closure-{index:02}", institute_id=institute,
                employee_id="emp-angela", service_id="svc-aisselles", customer_name="Legacy closure fixture",
                phone="+33999111222", start_time=start, end_time=start+timedelta(minutes=10), status="scheduled"))
        db.add(Appointment(id="browser-closure-legacy", institute_id=institute, employee_id="emp-angela",
            service_id="svc-aisselles", customer_name="Undated legacy closure", start_time=at,
            end_time=at+timedelta(minutes=10), status="cancelled"))
        for index, (currency, amount) in enumerate((("CHF", "1.01"), ("EUR", "2.02"), (None, "3.03"), ("CHF", None))):
            db.add(QueueTicket(id=f"browser-walk-closure-{index}", institute_id=institute,
                ticket_number=f"browser-walk-{index}", arrival_time=at, status="waiting",
                currency=currency, total_amount=Decimal(amount) if amount else None))
        db.commit()
        for index in range(25):
            action = bookings.cancel_appointment if index % 2 == 0 else bookings.mark_appointment_no_show
            action(db, f"browser-closure-{index:02}", "browser-manager")
        for index in range(4):
            tickets.cancel_ticket(db, f"browser-walk-closure-{index}", "browser-manager")
        db.add(QueueTicket(id="browser-walk-closure-legacy", institute_id=institute,
            ticket_number="browser-walk-legacy", arrival_time=at, status="cancelled"))
        db.flush()
        db.add(QueueEvent(institute_id=institute, ticket_id="browser-walk-closure-legacy",
            event_type="queue.cancelled", previous_status="waiting", status="cancelled", occurred_at=at))
        db.commit()


def read_closure_snapshot(engine):
    with Session(engine) as db:
        return dict(bookings=[dict(id=row.id, status=row.status) for row in db.scalars(select(Appointment)
            .where(Appointment.id.like("browser-closure-%")).order_by(Appointment.id))],
            booking_events=[dict(id=row.id, appointment_id=row.appointment_id, type=row.event_type,
                at=str(row.occurred_at), before=row.before, after=row.after)
                for row in db.scalars(select(BookingEvent).where(BookingEvent.appointment_id.like("browser-closure-%")).order_by(BookingEvent.id))],
            tickets=[dict(id=row.id, status=row.status, amount=str(row.total_amount), currency=row.currency)
                for row in db.scalars(select(QueueTicket).where(QueueTicket.id.like("browser-walk-closure-%")).order_by(QueueTicket.id))],
            queue_events=[dict(id=row.id, ticket_id=row.ticket_id, type=row.event_type, at=str(row.occurred_at), terms=row.cancellation_terms)
                for row in db.scalars(select(QueueEvent).where(QueueEvent.ticket_id.like("browser-walk-closure-%")).order_by(QueueEvent.id))])
