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
from app.modules.scheduling.service_4b import assignment_options_for_ticket
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


@router.get("/{ticket_id}/assignment-options")
def get_ticket_assignment_options(
    ticket_id: str,
    institute_id: str = Query(...),
    current_user: dict = Depends(require_ticket_manager),
    db: Session = Depends(get_db),
) -> dict:
    """
    Get assignment options for a waiting ticket (Phase 4B).
    
    Returns deterministic list of employees who can take the ticket,
    considering:
    - Employee availability (status, active sessions, appointments)
    - Service duration (must fit before next appointment)
    - Sorting: immediately assignable first, then by earliest start time
    
    Key principle: AVAILABLE != ASSIGNABLE
    An employee may be available but service duration may not fit in the window.
    
    Returns:
        {
            "ticket_id": str,
            "institute_id": str,
            "service_duration_minutes": int,
            "options": [
                {
                    "employee_id": str,
                    "employee_name": str,
                    "assignable": bool,
                    "available_from": str (ISO 8601),
                    "available_until": str (ISO 8601) or null,
                    "service_duration_minutes": int,
                    "projected_end_time": str (ISO 8601) or null,
                    "reason": str,
                    "blocking_appointment_id": str or null,
                    "blocking_session_id": str or null,
                },
                ...
            ]
        }
    """
    # Tenant scope check
    if current_user.get("institute_id") != institute_id:
        raise HTTPException(status_code=403, detail="Unauthorized access to institute")
    
    try:
        options = assignment_options_for_ticket(db, institute_id, ticket_id)
    except NotFound:
        raise HTTPException(status_code=404, detail="Ticket not found")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    
    service_duration = options[0].service_duration_minutes if options else 0
    
    return {
        "ticket_id": ticket_id,
        "institute_id": institute_id,
        "service_duration_minutes": service_duration,
        "options": [o.to_dict() for o in options],
    }
