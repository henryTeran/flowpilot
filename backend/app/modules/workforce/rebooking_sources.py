"""Capture validated inputs for an explicit rebooking declaration.

Caller must hold the institute transaction lock; this module neither writes a
declaration nor infers one from chronology. No customer identity is guessed.
"""
from datetime import datetime
from typing import Literal
from pydantic import AwareDatetime, BaseModel
from sqlalchemy import select
from app.modules.appointments.models import Appointment, BookingEvent
from app.modules.planning.models import ServiceSession
from app.modules.tickets.models import TicketLine, QueueTicket
from app.modules.customers.models import Customer
from app.modules.employees.models import Employee
from app.shared.exceptions import business_error
from app.shared.time import explicit_utc_instant


class ExecutionCapture(BaseModel):
    kind: Literal["session", "appointment"]
    id: str
    employee_id: str
    service_id: str
    customer_id: str
    actual_start: AwareDatetime
    actual_end: AwareDatetime


class BookingCapture(BaseModel):
    appointment_id: str
    creation_event_id: str
    created_at: AwareDatetime
    original_start: AwareDatetime
    original_end: AwareDatetime
    current_start: AwareDatetime
    current_end: AwareDatetime


def execution(db, institute, kind, identifier, now):
    if kind == "session":
        source = db.scalar(select(ServiceSession).where(ServiceSession.institute_id == institute, ServiceSession.id == identifier))
        first, last = (source.start_time, source.real_end_time) if source else (None, None)
        # Explicit owned line/ticket links only, never invoice cashier or names.
        customer = db.scalar(select(QueueTicket.customer_id).join(TicketLine, TicketLine.ticket_id == QueueTicket.id)
            .where(QueueTicket.institute_id == institute, TicketLine.id == source.ticket_line_id)) if source else None
    elif kind == "appointment":
        source = db.scalar(select(Appointment).where(Appointment.institute_id == institute, Appointment.id == identifier))
        first, last = (source.actual_start_time, source.actual_end_time) if source else (None, None)
        customer = source.customer_id if source else None
    else:
        raise business_error("Source de prestation inconnue")
    first = explicit_utc_instant(first) if first else None
    last = explicit_utc_instant(last) if last else None
    if source is None or source.status != "completed" or first is None or last is None or last <= first or last > now:
        raise business_error("Le rebooking exige une prestation terminee avec des instants effectifs coherents")
    if db.scalar(select(Employee.id).where(Employee.institute_id == institute, Employee.id == source.employee_id)) is None:
        raise business_error("Executante de cet institut requise")
    if not customer or db.scalar(select(Customer.id).where(Customer.institute_id == institute, Customer.id == customer)) is None:
        raise business_error("Le rebooking exige un lien client explicite de cet institut")
    return ExecutionCapture(kind=kind, id=source.id, employee_id=source.employee_id, service_id=source.service_id,
        customer_id=customer, actual_start=first, actual_end=last)


def _instant(value):
    # Booking snapshots are ISO text, never numeric epochs or naive clocks.
    if not isinstance(value, str): raise ValueError()
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None: raise ValueError()
    return explicit_utc_instant(parsed)


def booking(db, institute, identifier, source: ExecutionCapture, now):
    target = db.scalar(select(Appointment).where(Appointment.institute_id == institute, Appointment.id == identifier))
    # Never guess a creation date from the planned slot. Ambiguous legacy events
    # cannot support an original declaration, even if their visible slot matches.
    events = list(db.scalars(select(BookingEvent).where(BookingEvent.institute_id == institute,
        BookingEvent.appointment_id == identifier, BookingEvent.event_type == "created").limit(2)))
    return capture_booking(target, events, source, now)


def capture_booking(target, events, source: ExecutionCapture, now):
    if target is None or target.status not in {"scheduled", "confirmed", "arrived", "in_progress", "completed"} or target.customer_id != source.customer_id:
        raise business_error("Reservation active et lien client identique requis")
    if source.kind == "appointment" and target.id == source.id:
        raise business_error("Une prestation ne peut pas etre son propre rebooking")
    if len(events) != 1:
        raise business_error("Provenance de creation de la reservation inconnue ou ambigue")
    event = events[0]
    try:
        created = explicit_utc_instant(event.occurred_at)
        original_start, original_end = _instant(event.after["start_time"]), _instant(event.after["end_time"])
        current_start, current_end = explicit_utc_instant(target.booked_start_time), explicit_utc_instant(target.booked_end_time)
        valid = event.after["customer_id"] == source.customer_id and event.after["status"] == "scheduled" \
            and source.actual_end <= created <= now and original_end > original_start > created \
            and current_end > current_start > source.actual_end
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
        valid = False
    if not valid:
        raise business_error("La reservation doit avoir ete creee apres la prestation pour ce meme client")
    return BookingCapture(appointment_id=target.id, creation_event_id=event.id, created_at=created,
        original_start=original_start, original_end=original_end, current_start=current_start, current_end=current_end)
