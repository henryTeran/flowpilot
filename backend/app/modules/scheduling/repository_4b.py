"""
Scheduling repository — Phase 4B: Queue Assignment Options

Deterministic assignment logic: AVAILABLE != ASSIGNABLE
An employee may be available but service duration may not fit before next appointment.
"""

from datetime import datetime, timedelta, timezone
import math
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.appointments.models import Appointment
from app.modules.employees.models import Employee
from app.modules.planning.models import ServiceSession
from app.modules.scheduling.models import (
    AvailabilityReason,
    AvailabilityResult,
    AvailabilitySlot,
    AssignmentOption,
)
from app.modules.tickets.models import QueueTicket, TicketLine
from app.shared.exceptions import not_found


# Reused status constants
ACTIVE_SESSION_STATUSES = ["planned", "in_progress", "extended", "delayed"]
ACTIVE_APPOINTMENT_STATUSES = ["scheduled", "confirmed", "arrived", "in_progress"]
UNAVAILABLE_EMPLOYEE_STATUSES = {"pause", "absent", "offline"}


def get_employee_by_id(db: Session, employee_id: str) -> Employee | None:
    """Get employee by ID."""
    return db.get(Employee, employee_id)


def get_active_session(db: Session, institute_id: str, employee_id: str) -> ServiceSession | None:
    """Get active service session for employee."""
    return db.scalars(
        select(ServiceSession).where(
            ServiceSession.institute_id == institute_id,
            ServiceSession.employee_id == employee_id,
            ServiceSession.status.in_(ACTIVE_SESSION_STATUSES),
        )
    ).first()


def get_current_appointment(db: Session, institute_id: str, employee_id: str, now: datetime) -> Appointment | None:
    """Get appointment currently occupying employee (overlaps with now)."""
    return db.scalars(
        select(Appointment).where(
            Appointment.institute_id == institute_id,
            Appointment.employee_id == employee_id,
            Appointment.status.in_(ACTIVE_APPOINTMENT_STATUSES),
            Appointment.start_time <= now,
            Appointment.end_time > now,
        )
    ).first()


def get_next_appointment(db: Session, institute_id: str, employee_id: str, after: datetime) -> Appointment | None:
    """Get next appointment after given time."""
    return db.scalars(
        select(Appointment).where(
            Appointment.institute_id == institute_id,
            Appointment.employee_id == employee_id,
            Appointment.status.in_(ACTIVE_APPOINTMENT_STATUSES),
            Appointment.start_time > after,
        ).order_by(Appointment.start_time)
    ).first()


def get_upcoming_appointments(
    db: Session, institute_id: str, employee_id: str, after: datetime, limit: int = 5
) -> list[Appointment]:
    """Get upcoming appointments after given time."""
    return list(
        db.scalars(
            select(Appointment).where(
                Appointment.institute_id == institute_id,
                Appointment.employee_id == employee_id,
                Appointment.status.in_(ACTIVE_APPOINTMENT_STATUSES),
                Appointment.start_time > after,
            ).order_by(Appointment.start_time).limit(limit)
        ).all()
    )


def list_employees_by_institute(db: Session, institute_id: str) -> list[Employee]:
    """Get all employees in institute."""
    return list(
        db.scalars(
            select(Employee).where(Employee.institute_id == institute_id)
        ).all()
    )


def get_ticket_with_lines(db: Session, ticket_id: str) -> tuple[QueueTicket, list[TicketLine]] | None:
    """Get ticket and its service lines."""
    ticket = db.get(QueueTicket, ticket_id)
    if not ticket:
        return None
    lines = list(
        db.scalars(
            select(TicketLine).where(TicketLine.invoice_removed_at.is_(None)).where(TicketLine.ticket_id == ticket_id)
        ).all()
    )
    return ticket, lines


def calculate_ticket_duration(lines: list[TicketLine]) -> int:
    """Calculate total service duration for ticket (sum of line durations)."""
    return sum(line.duration_minutes * line.quantity for line in lines)


def _ensure_aware(value: datetime | None) -> datetime | None:
    """Ensure datetime is UTC-aware."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _minutes_until(target: datetime | None, now: datetime) -> int:
    """Calculate minutes from now until target time."""
    if target is None:
        return 0
    target = _ensure_aware(target)
    now = _ensure_aware(now)
    delta = target - now
    return max(0, math.ceil(delta.total_seconds() / 60))
