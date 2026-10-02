"""
Scheduling routes — Phase 4A: Availability Engine

Deterministic endpoints:
- GET /employees/{employee_id}/availability — Single employee availability
- GET /institutes/{institute_id}/availability/pool — Assignment options for all employees
"""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.permissions import require_ticket_manager
from app.database.session import get_db
from app.modules.scheduling.service import (
    availability_engine,
    availability_pool,
)
from app.modules.scheduling.models import AvailabilityResult

router = APIRouter(prefix="/availability", tags=["scheduling"])


@router.get("/employees/{employee_id}")
def get_employee_availability(
    employee_id: str,
    institute_id: str = Query(...),
    service_id: str | None = None,
    current_user: dict = Depends(require_ticket_manager),
    db: Session = Depends(get_db),
) -> dict:
    """
    Get availability for a single employee.
    
    Returns:
        {
            "employee_id": str,
            "institute_id": str,
            "available": bool,
            "current_slot": AvailabilitySlot,
            "upcoming_slots": [AvailabilitySlot, ...],
        }
    """
    # Tenant scope check
    if current_user.get("institute_id") != institute_id:
        raise HTTPException(status_code=403, detail="Unauthorized access to institute")
    
    result = availability_engine(db, institute_id, employee_id, service_id)
    return result.to_dict()


@router.get("/institutes/{institute_id}/pool")
def get_availability_pool(
    institute_id: str,
    service_id: str | None = None,
    current_user: dict = Depends(require_ticket_manager),
    db: Session = Depends(get_db),
) -> dict:
    """
    Get availability for all employees in institute (assignment options).
    
    Returns:
        {
            "institute_id": str,
            "employees": [AvailabilityResult, ...],  # Sorted by availability
        }
    """
    # Tenant scope check
    if current_user.get("institute_id") != institute_id:
        raise HTTPException(status_code=403, detail="Unauthorized access to institute")
    
    results = availability_pool(db, institute_id, service_id)
    return {
        "institute_id": institute_id,
        "employees": [r.to_dict() for r in results],
    }
