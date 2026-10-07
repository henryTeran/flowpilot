from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import AwareDatetime
from sqlalchemy.orm import Session
from app.core.permissions import require_ticket_manager
from app.database.session import get_db
from app.modules.revenue import billing, sources, capacity, closures, scenarios

router = APIRouter(prefix="/revenue/institutes/{institute_id}", tags=["revenue"])


def manager(institute_id: str, user=Depends(require_ticket_manager)):
    if user.get("institute_id") != institute_id or user.get("role") != "responsable_institut":
        raise HTTPException(403, "Permission insuffisante")
    return user


@router.get("/billing", response_model=billing.Billing)
def recorded_billing(institute_id: str, start: AwareDatetime, end: AwareDatetime,
    user=Depends(manager), db: Session = Depends(get_db)):
    return sources.read(db, institute_id, start, end)


@router.get("/capacity", response_model=capacity.Capacity)
def recorded_capacity(institute_id: str, day: date, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=50),
    user=Depends(manager), db: Session = Depends(get_db)):
    return capacity.read(db, institute_id, day, offset, limit)


@router.get("/booking-closures", response_model=closures.Closures)
def booking_closures(institute_id: str, start: AwareDatetime, end: AwareDatetime,
    offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=50),
    user=Depends(manager), db: Session = Depends(get_db)):
    return closures.read(db, institute_id, start, end, offset, limit)


@router.post("/scenarios/revenue-preview", response_model=scenarios.Scenario)
def revenue_scenario(institute_id: str, request: scenarios.Request, user=Depends(manager), db: Session = Depends(get_db)):
    return scenarios.preview(db, institute_id, request, user.get("sub"))
