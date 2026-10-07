"""Recorded booking closures and explicit, noncausal follow-up opportunities."""
from datetime import datetime, timezone
from typing import Literal
from pydantic import AwareDatetime, field_validator
from sqlalchemy import select, func
from app.modules.appointments.models import Appointment, BookingEvent
from app.modules.appointments.events import snapshot
from app.modules.employees.models import Employee
from app.modules.crm.metrics import Fact, Identifier, Count
from app.modules.revenue.billing import Window
from app.modules.tickets.repository import lock_institute
from app.modules.workforce.schemas import MatrixPage
from app.shared.exceptions import business_error
from app.shared.time import utcnow, explicit_utc_instant


class BookingSnapshot(Fact):
    status: Literal["scheduled", "confirmed", "arrived", "cancelled", "no_show"]
    employee_id: Identifier
    service_id: Identifier
    customer_id: Identifier | None
    start_time: AwareDatetime
    end_time: AwareDatetime
    booked_start_time: AwareDatetime | None
    booked_end_time: AwareDatetime | None
    actual_start_time: AwareDatetime | None
    actual_end_time: AwareDatetime | None
    checkout_ticket_id: Identifier | None

    @field_validator("*", mode="before")
    @classmethod
    def explicit_time(cls, value, info):
        if info.field_name.endswith("_time") and value is not None:
            if not isinstance(value, (datetime, str)) or isinstance(value, datetime) and value.utcoffset() is None \
                    or isinstance(value, str) and "T" not in value:
                raise ValueError("Explicit aware booking instants are required")
        return value


class Evidence(Fact):
    institute_id: Identifier
    event_id: Identifier
    appointment_id: Identifier
    event_type: Literal["cancelled", "no_show"]
    actor_id: str | None
    occurred_at: AwareDatetime
    captured_at: AwareDatetime
    before: BookingSnapshot
    after: BookingSnapshot
    retained_booking_price: None = None


class Opportunity(Fact):
    type: Literal["review_cancelled_booking", "review_no_show_booking"]
    evidence: Evidence
    estimated_value: None = None
    confidence: Literal["recorded_closure_only_unpriced"] = "recorded_closure_only_unpriced"
    recommended_action: Literal["review_booking_and_contact_permission_before_follow_up"] = "review_booking_and_contact_permission_before_follow_up"
    action_executed: Literal[False] = False

    @field_validator("action_executed", mode="before")
    @classmethod
    def no_execution(cls, value):
        if value is not False:
            raise ValueError("A read cannot execute follow-up")
        return value


class Closures(Fact):
    window: Window
    basis: Literal["booking_closure_event_time"] = "booking_closure_event_time"
    page: MatrixPage
    opportunities: tuple[Opportunity, ...]
    cancelled_count: Count
    no_show_count: Count
    unpriced_count: Count
    institute_terminal_bookings_without_closure_event: Count
    cancelled_revenue: None = None
    no_show_revenue: None = None
    causal_loss_proven: Literal[False] = False
    complete_booking_history: Literal[False] = False

    @field_validator("causal_loss_proven", "complete_booking_history", mode="before")
    @classmethod
    def no_claim(cls, value):
        if value is not False:
            raise ValueError("A closure event is not causal revenue loss")
        return value


def verify(evidence: Evidence, current: BookingSnapshot, window: Window):
    window = Window.model_validate(window.model_dump())
    evidence = Evidence.model_validate(evidence.model_dump())
    current = BookingSnapshot.model_validate(current.model_dump())
    if evidence.institute_id != window.institute_id or evidence.captured_at != window.captured_at \
            or not window.start <= evidence.occurred_at < window.end:
        raise ValueError("Closure scope and event clock must match the capture")
    before, after = evidence.before, evidence.after
    if before.status not in {"scheduled", "confirmed", "arrived"} or after.status != evidence.event_type \
            or after != current or before.start_time >= before.end_time:
        raise ValueError("Closure must retain a supported booking transition and current source")
    if before.model_dump(exclude={"status"}) != after.model_dump(exclude={"status"}) \
            or any(value is not None for value in (after.actual_start_time, after.actual_end_time, after.checkout_ticket_id)):
        raise ValueError("A closure cannot substitute booking or execution terms")
    return Opportunity(type="review_cancelled_booking" if evidence.event_type == "cancelled" else "review_no_show_booking", evidence=evidence)


def read(db, institute, start, end, offset=0, limit=20):
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 50:
        raise business_error("Invalid closure page bounds")
    lock_institute(db, institute)
    try:
        window = Window(institute_id=institute, start=start, end=end, captured_at=utcnow())
    except ValueError as error:
        raise business_error("An explicit observed closure period is required") from error
    counts = select(BookingEvent.appointment_id.label("appointment"), func.count().label("count")).where(
        BookingEvent.institute_id == institute, BookingEvent.event_type.in_(["cancelled", "no_show"])) \
        .group_by(BookingEvent.appointment_id).subquery()
    source = select(BookingEvent, Appointment, counts.c.count, Employee.id).outerjoin(Appointment,
        (Appointment.id == BookingEvent.appointment_id) & (Appointment.institute_id == BookingEvent.institute_id)) \
        .outerjoin(Employee, (Employee.id == Appointment.employee_id) & (Employee.institute_id == BookingEvent.institute_id)) \
        .join(counts, counts.c.appointment == BookingEvent.appointment_id).where(BookingEvent.institute_id == institute,
            BookingEvent.event_type.in_(["cancelled", "no_show"]),
            BookingEvent.occurred_at >= window.start.astimezone(timezone.utc),
            BookingEvent.occurred_at < window.end.astimezone(timezone.utc)).order_by(BookingEvent.occurred_at, BookingEvent.id)
    total = cancelled = no_show = 0
    rows = []
    try:
        for event, appointment, count, employee in db.execute(source.execution_options(yield_per=100)):
            if appointment is None or employee is None or count != 1:
                raise ValueError("A unique owned terminal booking source is required")
            opportunity = verify(Evidence(institute_id=institute, event_id=event.id, appointment_id=event.appointment_id,
                event_type=event.event_type, actor_id=event.actor_id, occurred_at=explicit_utc_instant(event.occurred_at),
                captured_at=window.captured_at, before=event.before, after=event.after),
                BookingSnapshot.model_validate(snapshot(appointment)), window)
            cancelled += event.event_type == "cancelled"
            no_show += event.event_type == "no_show"
            if offset <= total < offset+limit:
                rows.append(opportunity)
            total += 1
    except ValueError as error:
        raise business_error("Recorded closure sources require verification") from error
    missing = db.scalar(select(func.count()).select_from(Appointment).where(Appointment.institute_id == institute,
        Appointment.status.in_(["cancelled", "no_show"]), ~select(BookingEvent.id).where(
            BookingEvent.institute_id == institute, BookingEvent.appointment_id == Appointment.id,
            BookingEvent.event_type.in_(["cancelled", "no_show"])).exists()))
    return Closures(window=window, page=MatrixPage(offset=offset, limit=limit, total=total), opportunities=tuple(rows),
        cancelled_count=cancelled, no_show_count=no_show, unpriced_count=total,
        institute_terminal_bookings_without_closure_event=missing)
