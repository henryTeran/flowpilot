"""
Availability Engine Service (Phase 4A).

Deterministic rules for computing employee availability.
No AI, no predictions — only facts from database.
"""

from datetime import datetime, timezone
from math import ceil

from sqlalchemy.orm import Session

from app.modules.scheduling.models import (
    AvailabilityReason,
    AvailabilityResult,
    AvailabilitySlot,
)
from app.modules.scheduling import repository as repo
from app.shared.time import utcnow


def _ensure_aware(value: datetime) -> datetime:
    """Ensure datetime is timezone-aware (UTC)."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _minutes_until(target: datetime | None, now: datetime) -> int | None:
    """Calculate minutes from now until target time."""
    if target is None:
        return None
    delta_seconds = (_ensure_aware(target) - _ensure_aware(now)).total_seconds()
    return max(0, ceil(delta_seconds / 60))


def availability_engine(
    db: Session,
    institute_id: str,
    employee_id: str,
    service_id: str | None = None,
    now: datetime | None = None,
) -> AvailabilityResult:
    """
    Compute employee availability deterministically.
    
    Rules (strictly deterministic):
    1. If employee status is pause/absent/offline → unavailable (blocked state)
    2. If employee has active session → unavailable until session ends
    3. If employee has current appointment → unavailable until appointment ends
    4. Otherwise → available now
    5. Check next appointment to see future unavailability
    
    Args:
        db: Database session
        institute_id: Institute scope (tenant isolation)
        employee_id: Which employee to check
        service_id: Optional service to check compatibility (Phase 5: skills)
        now: Current time (default: utcnow)
    
    Returns:
        AvailabilityResult with current/upcoming slots and availability flag
    """
    if now is None:
        now = utcnow()
    
    # Query employee record
    employee = repo.get_employee_by_id(db, employee_id)
    if not employee or employee.institute_id != institute_id:
        # Employee doesn't exist or wrong institute
        return AvailabilityResult(
            employee_id=employee_id,
            institute_id=institute_id,
            service_id=service_id,
            available=False,
            current_slot=AvailabilitySlot(
                employee_id=employee_id,
                institute_id=institute_id,
                available_from=now,
                available_until=None,
                reason=AvailabilityReason.EMPLOYEE_OFFLINE,
            ),
        )
    
    now = _ensure_aware(now)
    
    # Rule 1: Check employee status (pause, absent, offline)
    if employee.status in repo.UNAVAILABLE_EMPLOYEE_STATUSES:
        reason_map = {
            "pause": AvailabilityReason.EMPLOYEE_PAUSE,
            "absent": AvailabilityReason.EMPLOYEE_ABSENT,
            "offline": AvailabilityReason.EMPLOYEE_OFFLINE,
        }
        return AvailabilityResult(
            employee_id=employee_id,
            institute_id=institute_id,
            service_id=service_id,
            available=False,
            current_slot=AvailabilitySlot(
                employee_id=employee_id,
                institute_id=institute_id,
                available_from=now,
                available_until=None,
                reason=reason_map.get(employee.status, AvailabilityReason.EMPLOYEE_OFFLINE),
            ),
        )
    
    # Rule 2: Check active session (in_progress, planned, extended, delayed)
    active_session = repo.get_active_session(db, institute_id, employee_id)
    if active_session:
        available_from = _ensure_aware(active_session.planned_end_time)
        return AvailabilityResult(
            employee_id=employee_id,
            institute_id=institute_id,
            service_id=service_id,
            available=False,
            current_slot=AvailabilitySlot(
                employee_id=employee_id,
                institute_id=institute_id,
                available_from=available_from,
                available_until=None,
                reason=AvailabilityReason.IN_PROGRESS_SESSION,
                blocking_session_id=active_session.id,
            ),
        )
    
    # Rule 3: Check current appointment (overlapping with now)
    current_appointment = repo.get_current_appointment(db, institute_id, employee_id, now)
    if current_appointment:
        available_from = _ensure_aware(current_appointment.end_time)
        return AvailabilityResult(
            employee_id=employee_id,
            institute_id=institute_id,
            service_id=service_id,
            available=False,
            current_slot=AvailabilitySlot(
                employee_id=employee_id,
                institute_id=institute_id,
                available_from=available_from,
                available_until=None,
                reason=AvailabilityReason.UPCOMING_APPOINTMENT,
                blocking_appointment_id=current_appointment.id,
            ),
        )
    
    # Rule 4: Employee is available now
    current_slot = AvailabilitySlot(
        employee_id=employee_id,
        institute_id=institute_id,
        available_from=now,
        available_until=None,
        reason=AvailabilityReason.AVAILABLE_NOW,
    )
    
    # Rule 5: Check next appointment to bound availability
    next_appointment = repo.get_next_appointment(db, institute_id, employee_id, now)
    if next_appointment:
        current_slot.available_until = _ensure_aware(next_appointment.start_time)
    
    # Gather upcoming slots for reference
    upcoming_appointments = repo.get_upcoming_appointments(
        db, institute_id, employee_id, now, limit=5
    )
    upcoming_slots = []
    for appt in upcoming_appointments:
        slot = AvailabilitySlot(
            employee_id=employee_id,
            institute_id=institute_id,
            available_from=_ensure_aware(appt.end_time),
            available_until=None,
            reason=AvailabilityReason.UPCOMING_APPOINTMENT,
            blocking_appointment_id=appt.id,
        )
        # If there's another appointment after this, bound this slot
        idx = upcoming_appointments.index(appt)
        if idx + 1 < len(upcoming_appointments):
            next_appt = upcoming_appointments[idx + 1]
            slot.available_until = _ensure_aware(next_appt.start_time)
        upcoming_slots.append(slot)
    
    return AvailabilityResult(
        employee_id=employee_id,
        institute_id=institute_id,
        service_id=service_id,
        available=True,
        current_slot=current_slot,
        upcoming_slots=upcoming_slots,
    )


def availability_pool(
    db: Session,
    institute_id: str,
    service_id: str | None = None,
    now: datetime | None = None,
) -> list[AvailabilityResult]:
    """
    Get availability for all employees in institute.
    
    Used for showing assignment options to operator.
    """
    if now is None:
        now = utcnow()
    
    employees = repo.list_employees_by_institute(db, institute_id)
    results = [
        availability_engine(db, institute_id, emp.id, service_id, now)
        for emp in employees
    ]
    
    # Sort by availability: available first, then by earliest available time
    def sort_key(result: AvailabilityResult):
        if result.available:
            return (0, _ensure_aware(result.current_slot.available_from).timestamp())
        else:
            return (1, _ensure_aware(result.current_slot.available_from).timestamp())
    
    return sorted(results, key=sort_key)


def next_available_time_for_employee(
    db: Session,
    institute_id: str,
    employee_id: str,
    now: datetime | None = None,
) -> datetime:
    """
    When will this employee be available?
    
    Returns:
        - now if available now
        - end_time of blocking session/appointment otherwise
    """
    if now is None:
        now = utcnow()
    
    result = availability_engine(db, institute_id, employee_id, now=now)
    if result.current_slot:
        return _ensure_aware(result.current_slot.available_from)
    return _ensure_aware(now)


def earliest_available_employee(
    db: Session,
    institute_id: str,
    service_id: str | None = None,
    now: datetime | None = None,
) -> tuple[str, datetime] | None:
    """
    Which employee can start work soonest?
    
    Returns:
        (employee_id, available_from_time) or None if no available employees
    """
    if now is None:
        now = utcnow()
    
    results = availability_pool(db, institute_id, service_id, now)
    
    for result in results:
        if result.available or result.current_slot:
            return (
                result.employee_id,
                _ensure_aware(result.current_slot.available_from),
            )
    
    return None
