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
    

@dataclass
class AvailabilitySlot:
    """A deterministic availability window for an employee."""
    
    employee_id: str
    institute_id: str
    available_from: datetime  # When employee becomes available (ISO 8601 aware)
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
            "available_from": self.available_from.isoformat(),
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
    """Assignment option for a ticket: which employee can take it, when, how long to wait."""
    
    employee_id: str
    employee_name: str
    institute_id: str
    ticket_id: str
    service_id: str
    estimated_start_time: datetime  # When this employee would start the service
    estimated_wait_minutes: int  # How long client waits (0 if now)
    reason: str  # e.g., "available now", "busy until 14:45"
    
    def to_dict(self) -> dict:
        return {
            "employee_id": self.employee_id,
            "employee_name": self.employee_name,
            "institute_id": self.institute_id,
            "ticket_id": self.ticket_id,
            "service_id": self.service_id,
            "estimated_start_time": self.estimated_start_time.isoformat(),
            "estimated_wait_minutes": self.estimated_wait_minutes,
            "reason": self.reason,
        }
