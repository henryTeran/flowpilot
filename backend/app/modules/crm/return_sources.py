"""Locked actual-care source reads with whole-cohort metrics and bounded rows."""
from typing import Literal
from pydantic import ValidationError
from sqlalchemy import literal, or_, select, union_all
from app.modules.appointments.models import Appointment
from app.modules.crm.metrics import BillingWindow, Count, ExactRatio, Fact, Unsigned
from app.modules.crm.return_cycle import CareEpisode, CompletedCareFact, ReturnGap, calculate
from app.modules.customers.repository import require_customer
from app.modules.employees.models import Employee
from app.modules.planning.models import ServiceSession
from app.modules.tickets.models import QueueTicket, TicketLine
from app.modules.tickets.repository import lock_institute
from app.shared.exceptions import business_error
from app.shared.time import explicit_utc_instant, utcnow


class ReturnSummary(Fact):
    window: BillingWindow
    basis: Literal["recorded_completed_ticket_care"]
    execution_count: Count
    episode_count: Count
    known_gap_count: Count
    overlapping_gap_count: Count
    known_gap_total_us: Unsigned
    average_return_gap_us: ExactRatio | None
    complete_customer_history: Literal[False]
    inferred_booking_credit: Literal[False]


class ReturnPage(Fact):
    offset: Count
    limit: Count
    total: Count


class ReturnRead(Fact):
    complete_execution_coverage: Literal[False] = False
    complete_service_coverage: Literal[False] = False
    summary: ReturnSummary
    diagnostics: dict[Literal["unlinked_ticket", "invalid_owner_or_service", "invalid_actual_times"], Count]
    page: ReturnPage
    episodes: tuple[CareEpisode, ...]
    gaps: tuple[ReturnGap, ...]


def read(db, institute, customer, start, end, limit=20, offset=0):
    lock_institute(db, institute)
    require_customer(db, institute, customer)
    try:
        window = BillingWindow(institute_id=institute, customer_id=customer, start=start, end=end, captured_at=utcnow())
    except ValidationError as error:
        raise business_error("An explicit positive observed care window is required") from error
    result, diagnostics = capture(db, window)
    summary = ReturnSummary.model_validate(result.model_dump(exclude={"episodes", "gaps"}))
    if any(diagnostics.values()):
        summary = summary.model_copy(update={"average_return_gap_us": None})
    visible = result.episodes[offset:offset+limit]
    ticket_ids = {episode.ticket_id for episode in visible}
    return ReturnRead(summary=summary, diagnostics=diagnostics, page=ReturnPage(offset=offset, limit=limit, total=result.episode_count),
        episodes=visible, gaps=tuple(gap for gap in result.gaps if gap.next_ticket_id in ticket_ids))


def capture(db, window):
    """Caller owns institute lock and registered source; returns whole cohort."""
    institute, customer = window.institute_id, window.customer_id
    from datetime import timezone
    first, last, captured = (t.astimezone(timezone.utc) for t in (window.start, window.end, window.captured_at))
    def cohort(completion):
        # Undated and future completed sources cannot be assigned a guessed period.
        return or_(completion.is_(None), (completion >= first) & (completion < last), completion > captured)
    def performer(source):
        return select(Employee.id).where(Employee.id == source.employee_id,
            Employee.institute_id == institute).exists()
    sessions = select(literal("session"), ServiceSession.id, ServiceSession.service_id, QueueTicket.id,
        QueueTicket.institute_id, QueueTicket.customer_id, TicketLine.service_id,
        ServiceSession.start_time, ServiceSession.real_end_time, performer(ServiceSession))
    sessions = sessions.select_from(ServiceSession).join(TicketLine, TicketLine.id == ServiceSession.ticket_line_id).join(QueueTicket, QueueTicket.id == TicketLine.ticket_id).where(
        ServiceSession.institute_id == institute, QueueTicket.institute_id == institute,
        QueueTicket.customer_id == customer, ServiceSession.status == "completed", cohort(ServiceSession.real_end_time))
    appointments = select(literal("appointment"), Appointment.id, Appointment.service_id, QueueTicket.id,
        QueueTicket.institute_id, QueueTicket.customer_id, Appointment.service_id,
        Appointment.actual_start_time, Appointment.actual_end_time, performer(Appointment))
    appointments = appointments.select_from(Appointment).outerjoin(QueueTicket, QueueTicket.id == Appointment.checkout_ticket_id).where(
        Appointment.institute_id == institute, Appointment.customer_id == customer,
        Appointment.status == "completed", cohort(Appointment.actual_end_time))
    rows = db.execute(union_all(sessions, appointments).execution_options(yield_per=100))
    diagnostics = dict(unlinked_ticket=0, invalid_owner_or_service=0, invalid_actual_times=0)
    def facts():
        for kind, identity, service, ticket, owner, linked_customer, linked_service, began, finished, performer_owned in rows:
            if ticket is None:
                diagnostics["unlinked_ticket"] += 1
                continue
            if owner != institute or linked_customer != customer or linked_service != service or not performer_owned:
                diagnostics["invalid_owner_or_service"] += 1
                continue
            try:
                yield CompletedCareFact(institute_id=institute, customer_id=customer, ticket_id=ticket,
                    source_kind=kind, source_id=identity, service_id=service, actual_start_at=explicit_utc_instant(began),
                    actual_end_at=explicit_utc_instant(finished), captured_at=window.captured_at)
            except ValidationError:
                diagnostics["invalid_actual_times"] += 1
    result = calculate(window, facts())
    return result, diagnostics
