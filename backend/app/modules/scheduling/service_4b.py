"""
Scheduling service — Phase 4B: Queue Assignment Options

Deterministic assignment logic with service duration awareness.
Reuses Phase 4A availability engine.
"""

from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.modules.tickets.models import QueueTicket
from app.modules.scheduling.models import AssignmentOption
from app.modules.scheduling.service import availability_pool
from app.modules.scheduling.repository_4b import (
    get_ticket_with_lines,
    calculate_ticket_duration,
    get_employee_by_id,
    _ensure_aware,
)
from app.shared.time import utcnow


def _reasonfor_assignable(
    available: bool,
    reason: str,
    available_from: datetime | None,
    service_duration_minutes: int,
    available_until: datetime | None,
) -> tuple[bool, str]:
    """
    Determine if employee is assignable and why.
    
    AVAILABLE != ASSIGNABLE:
    - Employee must be available now or in near future
    - Service duration must fit in available window before next appointment
    
    Returns: (assignable: bool, reason: str)
    """
    if not available or available_from is None:
        # Not available at all
        return False, reason
    
    # Employee is available; check if service fits in window
    if available_until is None:
        # No upper bound; service fits
        return True, f"available from {available_from.strftime('%H:%M')}"
    
    # Calculate: does service fit before available_until?
    available_from = _ensure_aware(available_from)
    available_until = _ensure_aware(available_until)
    projected_end = available_from + timedelta(minutes=service_duration_minutes)
    
    if projected_end <= available_until:
        # Service fits!
        return True, f"available from {available_from.strftime('%H:%M')}"
    else:
        # Service doesn't fit before next appointment
        return False, f"service doesn't fit ({service_duration_minutes}min) before appointment at {available_until.strftime('%H:%M')}"


def assignment_options_for_ticket(
    db: Session,
    institute_id: str,
    ticket_id: str,
    now: datetime | None = None,
) -> list[AssignmentOption]:
    """
    Get assignment options for a waiting ticket.
    
    Returns list sorted:
    1. Immediately assignable employees first
    2. Then by earliest feasible start time
    3. Stable by employee_id (tie-breaker)
    
    Args:
        db: Database session
        institute_id: Institute ID (tenant scope)
        ticket_id: Ticket ID
        now: Current time (UTC), defaults to utcnow()
    
    Returns:
        List of AssignmentOption, sorted by assignability and time
    
    Raises:
        NotFound: If ticket not found or belongs to different institute
    """
    now = now or utcnow()
    now = _ensure_aware(now)
    
    # Load ticket and lines
    result = get_ticket_with_lines(db, ticket_id)
    if not result:
        raise ValueError(f"Ticket not found: {ticket_id}")
    
    ticket, lines = result
    
    # Tenant scope check
    if ticket.institute_id != institute_id:
        raise ValueError(f"Ticket not found in institute {institute_id}")
    if ticket.status not in {"waiting", "assigned"}:
        raise ValueError("Ticket is not waiting for assignment")
    
    # Calculate service duration
    service_duration = calculate_ticket_duration(lines)
    if service_duration <= 0:
        raise ValueError("Ticket has no service duration")
    
    # Get availability pool (Phase 4A)
    availability_results = availability_pool(db, institute_id, now=now)
    reserved_employees = set(db.scalars(select(QueueTicket.assigned_employee_id).where(
        QueueTicket.institute_id == institute_id,
        QueueTicket.status == "assigned",
        QueueTicket.id != ticket_id,
        QueueTicket.assigned_employee_id.is_not(None),
    )).all())
    
    # Build assignment options
    options: list[AssignmentOption] = []
    
    for avail_result in availability_results:
        employee = get_employee_by_id(db, avail_result.employee_id)
        if not employee:
            continue  # Should not happen, but skip if missing
        
        # Determine assignability with service duration awareness
        assignable, reason = _reasonfor_assignable(
            available=avail_result.available,
            reason=avail_result.current_slot.reason.value if avail_result.current_slot else "unknown",
            available_from=avail_result.current_slot.available_from if avail_result.current_slot else None,
            service_duration_minutes=service_duration,
            available_until=avail_result.current_slot.available_until if avail_result.current_slot else None,
        )
        if employee.status != "available":
            assignable, reason = False, "employee_unavailable"
        if employee.id in reserved_employees:
            assignable, reason = False, "employee_reserved"
        if ticket.assigned_employee_id and ticket.assigned_employee_id != employee.id:
            assignable, reason = False, "ticket_already_assigned"
        
        # Calculate projected end time
        available_from = avail_result.current_slot.available_from if avail_result.current_slot else None
        projected_end = available_from + timedelta(minutes=service_duration) if assignable and available_from else None
        
        option = AssignmentOption(
            employee_id=avail_result.employee_id,
            employee_name=employee.first_name,
            institute_id=institute_id,
            ticket_id=ticket_id,
            assignable=assignable,
            available_from=available_from,
            available_until=avail_result.current_slot.available_until if avail_result.current_slot else None,
            service_duration_minutes=service_duration,
            projected_end_time=projected_end,
            reason=reason,
            blocking_appointment_id=avail_result.current_slot.blocking_appointment_id if avail_result.current_slot else None,
            blocking_session_id=avail_result.current_slot.blocking_session_id if avail_result.current_slot else None,
        )
        options.append(option)
    
    # Sort deterministically:
    # 1. Assignable employees first
    # 2. Then by available_from time (earliest first)
    # 3. Stable by employee_id (tie-breaker)
    options.sort(
        key=lambda o: (
            not o.assignable,  # False (assignable) comes before True (not assignable)
            o.available_from is None,
            o.available_from or datetime.max.replace(tzinfo=timezone.utc),
            o.employee_id,
        )
    )
    
    return options
