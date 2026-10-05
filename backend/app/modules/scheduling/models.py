"""
Scheduling module models for Phase 4: Scheduling & Capacity Engine

Deterministic availability engine:
- Respects employee operational status (available, busy, pause, absent, offline)
- Checks active service sessions
- Checks appointments
- Produces structured availability slots
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class AvailabilityReason(str, Enum):
    """Why is an employee available or unavailable."""
    AVAILABLE_NOW = "available_now"
    IN_PROGRESS_SESSION = "in_progress_session"  # Employee busy with active session
    UPCOMING_APPOINTMENT = "upcoming_appointment"  # Appointment blocks employee
    EMPLOYEE_PAUSE = "employee_pause"  # Status = pause
    EMPLOYEE_ABSENT = "employee_absent"  # Status = absent
    EMPLOYEE_OFFLINE = "employee_offline"  # Status = offline
    BUSY_UNTIL = "busy_until"  # Will be available at specific time
    SESSION_OVERDUE = "session_overdue"
    CAPACITY_UNKNOWN = "capacity_unknown"
    SKILLS_MISSING = "skills_missing"
    RESOURCE_CAPACITY_UNKNOWN = "resource_capacity_unknown"
    RESOURCE_RESERVED = "resource_reserved"
    

@dataclass
class AvailabilitySlot:
    """A deterministic availability window for an employee."""
    
    employee_id: str
    institute_id: str
    available_from: datetime | None  # None when the remaining capacity is unknown
    available_until: datetime | None  # When employee will become unavailable (if known), else None
    reason: AvailabilityReason
    blocking_session_id: str | None = None  # ServiceSession.id if blocked by session
    blocking_appointment_id: str | None = None  # Appointment.id if blocked by appointment
    blocking_resource_id: str | None = None  # For Phase 5: room/equipment constraint
    
    def to_dict(self) -> dict:
        """Serialize to JSON-compatible dict."""
        return {
            "employee_id": self.employee_id,
            "institute_id": self.institute_id,
            "available_from": self.available_from.isoformat() if self.available_from else None,
            "available_until": self.available_until.isoformat() if self.available_until else None,
            "reason": self.reason.value,
            "blocking_session_id": self.blocking_session_id,
            "blocking_appointment_id": self.blocking_appointment_id,
            "blocking_resource_id": self.blocking_resource_id,
        }


@dataclass
class AvailabilityResult:
    """Result of availability engine query for a single employee."""
    
    employee_id: str
    institute_id: str
    service_id: str | None  # The service we're checking for
    available: bool  # True if employee can take work now or in near future
    current_slot: AvailabilitySlot | None  # Current/next available slot
    upcoming_slots: list[AvailabilitySlot] = None  # Future slots (if requested)
    
    def __post_init__(self):
        if self.upcoming_slots is None:
            self.upcoming_slots = []
    
    def to_dict(self) -> dict:
        """Serialize to JSON-compatible dict."""
        return {
            "employee_id": self.employee_id,
            "institute_id": self.institute_id,
            "service_id": self.service_id,
            "available": self.available,
            "current_slot": self.current_slot.to_dict() if self.current_slot else None,
            "upcoming_slots": [s.to_dict() for s in self.upcoming_slots],
        }


@dataclass
class AssignmentOption:
    """
    Assignment option for a ticket: whether an employee can take it, when, and why.
    
    Key principle: AVAILABLE != ASSIGNABLE
    An employee may be available now but the service duration may not fit before
    the next appointment. This model captures both availability and assignability.
    """
    
    employee_id: str
    employee_name: str
    institute_id: str
    ticket_id: str
    assignable: bool  # Can the full service duration fit in available window?
    available_from: datetime | None  # None when no start can be projected
    available_until: datetime | None  # When employee will become unavailable (if known)
    service_duration_minutes: int  # Total service duration for this ticket
    projected_end_time: datetime | None  # When service would end if assigned now (if assignable)
    reason: str  # Why: "available_now", "busy_until_14:45", "service_does_not_fit", etc.
    blocking_appointment_id: str | None = None  # Appointment blocking if not assignable
    blocking_session_id: str | None = None  # Session blocking if not assignable
    
    def to_dict(self) -> dict:
        return {
            "employee_id": self.employee_id,
            "employee_name": self.employee_name,
            "institute_id": self.institute_id,
            "ticket_id": self.ticket_id,
            "assignable": self.assignable,
            "available_from": self.available_from.isoformat() if self.available_from else None,
            "available_until": self.available_until.isoformat() if self.available_until else None,
            "service_duration_minutes": self.service_duration_minutes,
            "projected_end_time": self.projected_end_time.isoformat() if self.projected_end_time else None,
            "reason": self.reason,
            "blocking_appointment_id": self.blocking_appointment_id,
            "blocking_session_id": self.blocking_session_id,
        }
