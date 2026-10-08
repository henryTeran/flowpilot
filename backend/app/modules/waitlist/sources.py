"""Signed current source capture for a selected retained waitlist version."""
from datetime import datetime, timezone
from typing import Annotated, Literal
from pydantic import AwareDatetime, BeforeValidator
from sqlalchemy import select
from app.modules.waitlist import domain, lifecycle, originals
from app.modules.crm import lifecycle_originals, return_sources
from app.modules.crm.metrics import BillingWindow, Count
from app.modules.crm.return_cycle import CareEpisode
from app.modules.customers.models import Customer
from app.modules.employees.models import Employee
from app.modules.services.models import Service
from app.modules.appointments.models import Appointment
from app.modules.planning.models import ServiceSession
from app.modules.tickets.models import QueueTicket, TicketLine
from app.modules.resources.models import Resource, ResourceReservation
from app.modules.workforce.models import EmployeeAbsence, AbsenceCancellation
from app.modules.resources import repository as resources
from app.modules.resources.reservations import resource_timelines
from app.modules.scheduling.service import availability_engine
from app.modules.scheduling.waiting_service import waiting_projections
from app.modules.scheduling.availability_domain import free_windows
from app.modules.scheduling.repository import ACTIVE_APPOINTMENT_STATUSES, ACTIVE_SESSION_STATUSES
from app.modules.tickets.repository import lock_institute
from app.shared.time import utcnow, explicit_utc_instant
from app.shared.exceptions import business_error


def _explicit_horizon(value):
    if isinstance(value, str) and "T" in value or isinstance(value, datetime) and value.utcoffset() is not None:
        return value
    raise ValueError("An explicit aware ISO horizon is required")


Horizon = Annotated[AwareDatetime, BeforeValidator(_explicit_horizon)]


class Policy(domain.Fact):
    channel: Literal["email", "sms"]
    history_requirement: Literal["review_only", "observed_care_required", "no_recorded_care_required"]
    permission_requirement: Literal["review_only", "recorded_grant_required"]


class QueueSlot(domain.Fact):
    ticket_id: str
    employee_id: str
    start: AwareDatetime
    end: AwareDatetime
    resource_ids: tuple[str, ...]


class Evidence(domain.Fact):
    registered_at: AwareDatetime
    latest_care: CareEpisode | None
    observed_care_episodes: Count
    care_diagnostics: dict[str, Count]
    permission_original: lifecycle_originals.Original | None
    permission_reason: Literal["declaration_absent", "future_declaration", "current_declaration"]
    employee_reasons: dict[str, str]
    customer_booking_ids: tuple[str, ...]
    customer_session_ids: tuple[str, ...]
    waiting_tickets: Count
    queue_slots: tuple[QueueSlot, ...]
    unprojectable_queue_tickets: Count
    capacity_basis: Literal["recorded_employee_bookings_sessions_absences_and_resource_reservations"] = "recorded_employee_bookings_sessions_absences_and_resource_reservations"
    queue_basis: Literal["existing_core_queue_allocations_as_virtual_blockers_not_reservations"] = "existing_core_queue_allocations_as_virtual_blockers_not_reservations"
    opening_hours: Literal["not_verified"] = "not_verified"
    contact_authority: Literal["not_granted_by_this_read"] = "not_granted_by_this_read"
    history_coverage: Literal["recorded_ticket_care_since_registration_not_complete_real_history"] = "recorded_ticket_care_since_registration_not_complete_real_history"


class Read(domain.Fact):
    state: lifecycle.State
    captured_at: AwareDatetime
    horizon_end: AwareDatetime
    policy: Policy
    review: domain.Review | None
    evidence: Evidence | None
    unavailable_reason: Literal["cancelled", "registration_unavailable", "active_service_unavailable", "history_requirement_unmet", "permission_requirement_unmet"] | None
    action: Literal["review_then_revalidate_before_booking_or_contact"] = "review_then_revalidate_before_booking_or_contact"


def _interval(start, end):
    return domain.Window(start=explicit_utc_instant(start), end=explicit_utc_instant(end))


def _activity(db, institute, now):
    employees = set(db.scalars(select(Employee.id).where(Employee.institute_id == institute)))
    for row in db.scalars(select(Employee).where(Employee.institute_id == institute).execution_options(populate_existing=True)):
        if not isinstance(row.skills, list) or any(not isinstance(skill, str) or not skill for skill in row.skills):
            raise ValueError("Recorded employee skills require a typed source")
    services = set(db.scalars(select(Service.id)))
    appointments = list(db.scalars(select(Appointment).where(Appointment.institute_id == institute,
        Appointment.status.in_(ACTIVE_APPOINTMENT_STATUSES)).execution_options(populate_existing=True)))
    sessions = list(db.scalars(select(ServiceSession).where(ServiceSession.institute_id == institute,
        ServiceSession.status.in_(ACTIVE_SESSION_STATUSES)).execution_options(populate_existing=True)))
    tickets = {row.id: row for row in db.scalars(select(QueueTicket).where(QueueTicket.institute_id == institute)
        .execution_options(populate_existing=True))}
    lines = {row.id: row for row in db.scalars(select(TicketLine).join(QueueTicket, QueueTicket.id == TicketLine.ticket_id)
        .where(QueueTicket.institute_id == institute).execution_options(populate_existing=True))}
    for row in appointments:
        if row.employee_id not in employees or row.service_id not in services:
            raise ValueError("Active booking requires owned employee and existing service")
        _interval(row.start_time, row.end_time)
    for row in sessions:
        if row.employee_id not in employees or row.service_id not in services or type(row.duration_minutes) is not int or row.duration_minutes <= 0:
            raise ValueError("Active session requires owned employee and valid service/duration")
        _interval(row.start_time, row.planned_end_time)
        if row.ticket_line_id is not None and (row.ticket_line_id not in lines or lines[row.ticket_line_id].service_id != row.service_id):
            raise ValueError("Session ticket source requires verification")
    absences = {row.id: row for row in db.scalars(select(EmployeeAbsence).where(EmployeeAbsence.institute_id == institute)
        .execution_options(populate_existing=True))}
    for row in absences.values():
        if row.employee_id not in employees or explicit_utc_instant(row.created_at) > now:
            raise ValueError("Absence requires owned employee and observed declaration")
        _interval(row.start_time, row.end_time)
    for row in db.scalars(select(AbsenceCancellation).where(AbsenceCancellation.institute_id == institute)
            .execution_options(populate_existing=True)):
        if row.absence_id not in absences or explicit_utc_instant(row.created_at) > now:
            raise ValueError("Absence cancellation requires an owned observed original")
    # Validate the entire active reservation cohort before a core reader can hide
    # an orphan or foreign resource; old unreleased occupancy stays unknown.
    owned_resources = set()
    for row in db.scalars(select(Resource).where(Resource.institute_id == institute).execution_options(populate_existing=True)):
        if row.status not in {"active", "inactive", "maintenance"} or not isinstance(row.capabilities, list) \
                or any(not isinstance(capability, str) for capability in row.capabilities):
            raise ValueError("Resource configuration requires a typed current source")
        owned_resources.add(row.id)
    booking_ids = set(db.scalars(select(Appointment.id).where(Appointment.institute_id == institute)))
    for row in db.scalars(select(ResourceReservation).where(ResourceReservation.institute_id == institute,
            ResourceReservation.status != "released").execution_options(populate_existing=True)):
        if row.status not in {"reserved", "in_use"} or row.resource_id not in owned_resources or (row.ticket_id is None) == (row.appointment_id is None) \
                or row.ticket_id is not None and row.ticket_id not in tickets \
                or row.appointment_id is not None and row.appointment_id not in booking_ids:
            raise ValueError("Reservation requires an owned resource and exactly one owned source")
        _interval(row.start_time, row.end_time)
    return appointments, sessions, tickets, lines


def read(db, institute, root_id, expected_event_id, expected_event_fingerprint, horizon_end, policy: Policy, *, _captured_at=None):
    try:
        policy = Policy.model_validate(policy.model_dump())
        lock_institute(db, institute)
        # Internal aggregate readers share one locked capture; HTTP callers cannot
        # supply an observation clock or capacity snapshot.
        now = _captured_at if _captured_at is not None else utcnow()
        if not isinstance(now, datetime) or now.utcoffset() is None:
            raise ValueError("An aware server capture is required")
        now = now.astimezone(timezone.utc)
        if not isinstance(horizon_end, datetime) or horizon_end.utcoffset() is None or horizon_end <= now:
            raise ValueError("An explicit positive future matching horizon is required")
        horizon_end = horizon_end.astimezone(timezone.utc)
        state = lifecycle._chain(db, institute, root_id, now)
        if state is None:
            raise business_error("An explicitly activated waitlist request is required")
        latest = state.events[-1]
        if (expected_event_id, expected_event_fingerprint) != (latest.original["id"], latest.fingerprint):
            raise business_error("Waitlist version changed; reread before matching")
        frame = dict(state=state, captured_at=now, horizon_end=horizon_end, policy=policy)
        if state.state == "cancelled":
            return Read(**frame, review=None, evidence=None, unavailable_reason="cancelled")
        demand = originals.Original.model_validate(state.current_demand.original).demand
        customer = db.scalar(select(Customer).where(Customer.institute_id == institute, Customer.id == demand.customer_id)
            .execution_options(populate_existing=True))
        if customer is None or explicit_utc_instant(customer.created_at) > now:
            return Read(**frame, review=None, evidence=None, unavailable_reason="registration_unavailable")
        service = db.scalar(select(Service).where(Service.id == demand.service_id, Service.status == "active")
            .execution_options(populate_existing=True))
        if service is None:
            return Read(**frame, review=None, evidence=None, unavailable_reason="active_service_unavailable")
        registered = explicit_utc_instant(customer.created_at)
        care_diagnostics = dict(unlinked_ticket=0, invalid_owner_or_service=0, invalid_actual_times=0)
        episode_count, latest_care, history = 0, None, "unknown"
        if registered < now:
            care, care_diagnostics = return_sources.capture(db, BillingWindow(institute_id=institute,
                customer_id=customer.id, start=registered, end=now, captured_at=now))
            episode_count = care.episode_count
            if not any(care_diagnostics.values()):
                latest_care = max(care.episodes, key=lambda row: (row.completed_at, row.ticket_id), default=None)
                history = "observed" if latest_care else "no_recorded_care"
        pointer = lifecycle_originals.head(db, institute, customer.id)
        permission_original = lifecycle_originals.require(db, institute, customer.id, pointer.original_id) if pointer else None
        permission_reason = "declaration_absent" if permission_original is None else \
            "future_declaration" if permission_original.created_at > now else "current_declaration"
        permission, permission_at, permission_reference = "unknown", None, None
        if permission_reason == "current_declaration":
            declaration = next(row for row in permission_original.declaration.communications
                if row.channel == policy.channel and row.purpose == "service_follow_up")
            permission = declaration.permission
            if permission != "unknown":
                permission_at, permission_reference = permission_original.created_at, permission_original.id
        context = domain.CustomerContext(customer_id=customer.id, history=history,
            history_reference=latest_care.ticket_id if latest_care else None, history_at=latest_care.completed_at if latest_care else None,
            permission=permission, channel=policy.channel, permission_at=permission_at, permission_reference=permission_reference)
        appointments, sessions, tickets, lines = _activity(db, institute, now)
        queue = {key: ticket for key, ticket in tickets.items() if ticket.status in {"waiting", "assigned"}}
        owned_employees = set(db.scalars(select(Employee.id).where(Employee.institute_id == institute)))
        need_facts = resources.resource_requirement_facts(db, institute)
        service_facts = {row.id: row for row in db.scalars(select(Service).execution_options(populate_existing=True))}
        missing_configuration = set()
        for ticket in queue.values():
            if explicit_utc_instant(ticket.arrival_time) > now or ticket.assigned_employee_id is not None and ticket.assigned_employee_id not in owned_employees \
                    or ticket.status == "assigned" and ticket.assigned_employee_id is None:
                raise ValueError("Queued work requires observed arrival and owned assignment")
        for line in lines.values():
            if line.ticket_id not in queue or line.invoice_removed_at is not None:
                continue
            if line.service_id not in service_facts or type(line.quantity) is not int or line.quantity <= 0 \
                    or type(line.duration_minutes) is not int or line.duration_minutes <= 0:
                raise ValueError("Queued work requires valid service, quantity and duration")
            if service_facts[line.service_id].requires_machine and not need_facts.get(line.service_id):
                missing_configuration.add(line.ticket_id)
        queue_slots = []
        def capture_allocation(projection, allocation):
            interval = _interval(projection.estimated_start_time, projection.estimated_end_time)
            if projection.ticket_id not in queue or projection.employee_id not in owned_employees or interval.start < now \
                    or allocation.start != interval.start or allocation.end != interval.end:
                raise ValueError("Core queue allocation must bind owned work and captured interval")
            queue_slots.append(QueueSlot(ticket_id=projection.ticket_id, employee_id=projection.employee_id,
                start=interval.start, end=interval.end, resource_ids=allocation.resource_ids))
        projections = waiting_projections(db, institute, now=now, _allocation_observer=capture_allocation) if queue else {}
        if set(projections) != set(queue) or len({slot.ticket_id for slot in queue_slots}) != len(queue_slots):
            raise ValueError("Queue capture must preserve the complete owned cohort")
        unprojectable = {key for key, value in projections.items() if value.reason != "projected"} | missing_configuration
        queue_slots = [slot for slot in queue_slots if slot.ticket_id not in unprojectable]
        if len(queue_slots)+len(unprojectable) != len(queue):
            raise ValueError("Known queue allocations and unknown tickets must partition the cohort")
        blockers, booking_ids, session_ids, customer_capacity = [], [], [], "known"
        for row in appointments:
            if row.customer_id == customer.id:
                blockers.append(_interval(row.start_time, row.end_time)); booking_ids.append(row.id)
                if row.status == "in_progress" and explicit_utc_instant(row.end_time) <= now:
                    customer_capacity = "unknown"
        for row in sessions:
            line = lines.get(row.ticket_line_id)
            ticket = tickets.get(line.ticket_id) if line else None
            if ticket and ticket.customer_id == customer.id:
                blockers.append(_interval(row.start_time, row.planned_end_time)); session_ids.append(row.id)
                if explicit_utc_instant(row.planned_end_time) <= now:
                    customer_capacity = "unknown"
        for slot in queue_slots:
            if queue[slot.ticket_id].customer_id == customer.id:
                blockers.append(domain.Window(start=slot.start, end=slot.end))
        skill_facts = resources.skill_facts(db, institute)
        employees, employee_reasons = [], {}
        for employee_id in sorted(skill_facts):
            # Keep employee availability, then solve joint resource/customer fit in
            # the matching kernel, rather than losing a later customer intersection.
            available = availability_engine(db, institute, employee_id, now=now)
            windows = []
            overdue_booking = any(row.employee_id == employee_id and row.status == "in_progress"
                and explicit_utc_instant(row.end_time) <= now for row in appointments)
            for slot in [available.current_slot, *available.upcoming_slots]:
                if slot.institute_id != institute or slot.employee_id != employee_id:
                    raise ValueError("Core availability scope mismatch")
                if slot.available_from is None or overdue_booking:
                    continue
                start = max(now, explicit_utc_instant(slot.available_from))
                end = min(horizon_end, explicit_utc_instant(slot.available_until)) if slot.available_until else horizon_end
                if end > start:
                    virtual = [(slot.start, slot.end, slot.ticket_id) for slot in queue_slots if slot.employee_id == employee_id]
                    for begin, finish, _ in free_windows(start, virtual):
                        finish = min(finish, end) if finish is not None else end
                        if finish > begin:
                            windows.append(domain.Window(start=begin, end=finish))
            employee_reasons[employee_id] = "overdue_active_booking" if overdue_booking else available.current_slot.reason.value
            employees.append(domain.EmployeeCapacity(employee_id=employee_id, skills=tuple(sorted(skill_facts[employee_id])),
                state="known" if available.current_slot.available_from is not None and not overdue_booking else "unknown", windows=tuple(windows)))
        needs = resources.resource_requirement_facts(db, institute).get(service.id, [])
        inventory = tuple(domain.ResourceCapacity(resource_id=row.resource_id, kind=row.kind,
            capabilities=tuple(sorted(row.capabilities)), state="inactive" if not row.active else "active_known" if row.capacity_known else "unknown",
            reservations=tuple(domain.Window(start=start, end=end) for start, end in row.reservations)
                + tuple(domain.Window(start=slot.start, end=slot.end) for slot in queue_slots if row.resource_id in slot.resource_ids))
            for row in resource_timelines(db, institute, now=now))
        capture = domain.Capture(institute_id=institute, captured_at=now,
            service=domain.ServiceCapacity(service_id=service.id, duration_minutes=service.duration_min,
                required_skills=tuple(sorted(resources.requirement_facts(db, institute, [service.id]).get(service.id, set()))),
                needs=tuple(domain.Need(kind=kind, capability=capability, quantity=quantity) for kind, capability, quantity in sorted(needs)),
                resource_configuration="unknown" if service.requires_machine and not needs else "known"),
            employees=tuple(employees), resources=inventory, customer=context,
            customer_capacity=customer_capacity, customer_blockers=tuple(blockers), queue_capacity="unknown" if unprojectable else "known")
        review = domain.match(demand, capture)
        evidence = Evidence(registered_at=registered, latest_care=latest_care, observed_care_episodes=episode_count,
            care_diagnostics=care_diagnostics, permission_original=permission_original, permission_reason=permission_reason,
            employee_reasons=employee_reasons, customer_booking_ids=tuple(sorted(booking_ids)), customer_session_ids=tuple(sorted(session_ids)),
            waiting_tickets=len(queue), queue_slots=tuple(queue_slots), unprojectable_queue_tickets=len(unprojectable))
        reason = None
        if policy.history_requirement == "observed_care_required" and history != "observed" \
                or policy.history_requirement == "no_recorded_care_required" and history != "no_recorded_care":
            reason = "history_requirement_unmet"
        elif policy.permission_requirement == "recorded_grant_required" and permission != "granted":
            reason = "permission_requirement_unmet"
        # Preserve the computation for source inspection but expose no admissible
        # options when the explicitly selected review policy refuses them.
        if reason:
            review = None
        return Read(**frame, review=review, evidence=evidence, unavailable_reason=reason)
    except (ValueError, TypeError, KeyError, StopIteration, OverflowError) as error:
        raise business_error("Current waitlist matching sources require verification") from error
