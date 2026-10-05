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
from app.modules.scheduling.availability_domain import free_windows
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
    """Current availability and known future windows; unknown is never now."""
    now = _ensure_aware(now or utcnow())
    employee = repo.get_employee_by_id(db, employee_id)
    def unknown(reason, session_id=None):
        return AvailabilityResult(employee_id, institute_id, service_id, False,
            AvailabilitySlot(employee_id, institute_id, None, None, reason,
                             blocking_session_id=session_id))

    if not employee or employee.institute_id != institute_id:
        return unknown(AvailabilityReason.EMPLOYEE_OFFLINE)
    if employee.status not in {"available", "busy"}:
        reasons = {"pause": AvailabilityReason.EMPLOYEE_PAUSE,
                   "absent": AvailabilityReason.EMPLOYEE_ABSENT,
                   "offline": AvailabilityReason.EMPLOYEE_OFFLINE}
        return unknown(reasons.get(employee.status, AvailabilityReason.CAPACITY_UNKNOWN))

    sessions = repo.list_active_sessions(db, institute_id, employee_id)
    overdue = next((session for session in sessions
                    if _ensure_aware(session.planned_end_time) <= now), None)
    if overdue:
        return unknown(AvailabilityReason.SESSION_OVERDUE, overdue.id)
    appointments = repo.list_remaining_appointments(db, institute_id, employee_id, now)
    current_appointment = next((appt for appt in appointments
                               if _ensure_aware(appt.start_time) <= now), None)
    if employee.status == "busy" and not sessions and not current_appointment:
        return unknown(AvailabilityReason.CAPACITY_UNKNOWN)

    ready = max([now] + [_ensure_aware(session.planned_end_time) for session in sessions])
    windows = free_windows(ready, [(_ensure_aware(appt.start_time),
                                   _ensure_aware(appt.end_time), appt.id) for appt in appointments])
    active_session = max(sessions, key=lambda item: _ensure_aware(item.planned_end_time), default=None)
    if active_session:
        reason = AvailabilityReason.IN_PROGRESS_SESSION
    elif current_appointment:
        reason = AvailabilityReason.UPCOMING_APPOINTMENT
    else:
        reason = AvailabilityReason.AVAILABLE_NOW
    begin, end, previous_appointment = windows[0]
    current_slot = AvailabilitySlot(employee_id, institute_id, begin, end, reason,
        blocking_session_id=active_session.id if active_session else None,
        blocking_appointment_id=current_appointment.id if current_appointment else previous_appointment)
    upcoming = [AvailabilitySlot(employee_id, institute_id, begin, end,
                    AvailabilityReason.UPCOMING_APPOINTMENT, blocking_appointment_id=evidence_id)
                for begin, end, evidence_id in windows[1:]]
    return AvailabilityResult(employee_id, institute_id, service_id,
                              employee.status == "available" and begin == now,
                              current_slot, upcoming)


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
        start = result.current_slot.available_from if result.current_slot else None
        return (not result.available, start is None,
                start.timestamp() if start else float("inf"), result.employee_id)
    
    return sorted(results, key=sort_key)


def next_available_time_for_employee(
    db: Session,
    institute_id: str,
    employee_id: str,
    now: datetime | None = None,
) -> datetime | None:
    """
    When will this employee be available?
    
    Returns:
        - now if available now
        - end of the complete known blocking chain otherwise
        - None when remaining capacity is unknown
    """
    if now is None:
        now = utcnow()
    
    result = availability_engine(db, institute_id, employee_id, now=now)
    if result.current_slot and result.current_slot.available_from:
        return _ensure_aware(result.current_slot.available_from)
    return None


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
        if result.current_slot and result.current_slot.available_from is not None:
            return (
                result.employee_id,
                _ensure_aware(result.current_slot.available_from),
            )
    
    return None
