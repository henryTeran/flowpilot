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
    if service_id:
        from app.modules.resources.repository import qualifies_for_services
        if not qualifies_for_services(db, institute_id, employee_id, [service_id]):
            return unknown(AvailabilityReason.SKILLS_MISSING)

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
    from app.modules.workforce.absences import remaining
    absences = remaining(db, institute_id, now, employee_id)
    current_absence = next((row for row in absences if _ensure_aware(row.start_time) <= now), None)
    windows = free_windows(ready, [(_ensure_aware(appt.start_time),
                                   _ensure_aware(appt.end_time), appt.id) for appt in appointments]
                           + [(_ensure_aware(row.start_time), _ensure_aware(row.end_time), "absence:" + row.id) for row in absences])
    resource_delayed = False
    if service_id:
        from app.modules.resources.repository import resource_requirement_facts
        from app.modules.resources.reservations import resource_timelines
        from app.modules.resources.allocation_domain import ResourceNeed, next_resource_window
        from app.modules.services.models import Service
        needs = tuple(ResourceNeed(*need) for need in resource_requirement_facts(db, institute_id).get(service_id, []))
        if needs:
            service = db.get(Service, service_id)
            duration = (service.duration_max or service.duration_min) if service else 0
            if duration <= 0:
                return unknown(AvailabilityReason.RESOURCE_CAPACITY_UNKNOWN)
            resources = resource_timelines(db, institute_id, now=now)
            joint_windows = []
            for begin, end, evidence_id in windows:
                match = next_resource_window(resources, needs, begin, duration, latest_end=end)
                if match is None:
                    continue
                boundaries = [end] if end else []
                boundaries.extend(start for resource in resources if resource.resource_id in match.resource_ids
                                  for start, _ in resource.reservations if start > match.start)
                joint_windows.append((match.start, min(boundaries) if boundaries else None, evidence_id))
            if not joint_windows:
                return unknown(AvailabilityReason.RESOURCE_CAPACITY_UNKNOWN)
            resource_delayed = joint_windows[0][0] > windows[0][0]
            windows = joint_windows
    active_session = max(sessions, key=lambda item: _ensure_aware(item.planned_end_time), default=None)
    if active_session:
        reason = AvailabilityReason.IN_PROGRESS_SESSION
    elif current_appointment:
        reason = AvailabilityReason.UPCOMING_APPOINTMENT
    elif current_absence:
        reason = AvailabilityReason.SCHEDULED_ABSENCE
    else:
        reason = AvailabilityReason.AVAILABLE_NOW
    if resource_delayed:
        reason = AvailabilityReason.RESOURCE_RESERVED
    begin, end, previous_appointment = windows[0]
    current_slot = AvailabilitySlot(employee_id, institute_id, begin, end, reason,
        blocking_session_id=active_session.id if active_session else None,
        blocking_appointment_id=current_appointment.id if current_appointment else previous_appointment if previous_appointment and not previous_appointment.startswith("absence:") else None,
        blocking_absence_id=current_absence.id if current_absence else previous_appointment.removeprefix("absence:") if previous_appointment and previous_appointment.startswith("absence:") else None)
    upcoming = [AvailabilitySlot(employee_id, institute_id, begin, end,
                    AvailabilityReason.SCHEDULED_ABSENCE if evidence_id and evidence_id.startswith("absence:") else AvailabilityReason.UPCOMING_APPOINTMENT,
                    blocking_appointment_id=evidence_id if evidence_id and not evidence_id.startswith("absence:") else None,
                    blocking_absence_id=evidence_id.removeprefix("absence:") if evidence_id and evidence_id.startswith("absence:") else None)
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
