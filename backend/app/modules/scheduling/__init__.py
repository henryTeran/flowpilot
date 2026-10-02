"""
Scheduling module __init__.py

Phase 4: Scheduling & Capacity Engine
"""

from app.modules.scheduling.models import (
    AvailabilityReason,
    AvailabilityResult,
    AvailabilitySlot,
    AssignmentOption,
)
from app.modules.scheduling.service import (
    availability_engine,
    availability_pool,
    next_available_time_for_employee,
    earliest_available_employee,
)

__all__ = [
    "AvailabilityReason",
    "AvailabilityResult",
    "AvailabilitySlot",
    "AssignmentOption",
    "availability_engine",
    "availability_pool",
    "next_available_time_for_employee",
    "earliest_available_employee",
]
