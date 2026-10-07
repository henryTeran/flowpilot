from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import AwareDatetime
from sqlalchemy.orm import Session
from app.core.permissions import require_ticket_manager
from app.database.session import get_db
from app.modules.revenue import billing, sources, capacity, closures, scenarios, rebooking, slot_opportunities, walk_in_cancellations
from app.modules.revenue import booking_references
from app.modules.revenue import booking_valuation
from app.modules.revenue import scenario_originals

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


@router.post("/scenarios/originals", response_model=scenario_originals.Envelope)
def retain_revenue_scenario(institute_id: str, request: scenario_originals.Declaration, user=Depends(manager), db: Session = Depends(get_db)):
    return scenario_originals.create(db, institute_id, request, user.get("sub"))


@router.get("/scenarios/original-by-key", response_model=scenario_originals.Envelope | None)
def recover_revenue_scenario(institute_id: str, key: str = Query(min_length=1, max_length=120), user=Depends(manager), db: Session = Depends(get_db)):
    return scenario_originals.by_key(db, institute_id, key)


@router.get("/scenarios/originals", response_model=scenario_originals.Audit)
def audit_revenue_scenarios(institute_id: str, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=50),
    user=Depends(manager), db: Session = Depends(get_db)):
    return scenario_originals.audit(db, institute_id, offset, limit)


@router.get("/scenarios/originals/{original_id}", response_model=scenario_originals.Envelope)
def original_revenue_scenario(institute_id: str, original_id: str, user=Depends(manager), db: Session = Depends(get_db)):
    return scenario_originals.require(db, institute_id, original_id)


@router.get("/rebooking", response_model=rebooking.Rebooking)
def rebooking_opportunities(institute_id: str, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=50),
    user=Depends(manager), db: Session = Depends(get_db)):
    return rebooking.read(db, institute_id, offset, limit)


@router.get("/capacity-opportunity", response_model=slot_opportunities.Read)
def capacity_opportunity(institute_id: str, service_id: str, horizon_end: AwareDatetime,
    user=Depends(manager), db: Session = Depends(get_db)):
    return slot_opportunities.read(db, institute_id, service_id, horizon_end)


@router.get("/walk-in-cancellations", response_model=walk_in_cancellations.Read)
def walk_in_cancellations_read(institute_id: str, start: AwareDatetime, end: AwareDatetime,
    offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=50),
    user=Depends(manager), db: Session = Depends(get_db)):
    return walk_in_cancellations.read(db, institute_id, start, end, offset, limit)


@router.get("/appointments/{appointment_id}/price-references", response_model=booking_references.Read)
def booking_price_references(institute_id: str, appointment_id: str, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=50),
    user=Depends(manager), db: Session = Depends(get_db)):
    return booking_references.read(db, institute_id, appointment_id, offset, limit)


@router.post("/appointments/{appointment_id}/closure-value-preview", response_model=booking_valuation.Preview)
def booking_closure_value(institute_id: str, appointment_id: str, request: booking_valuation.Request,
    user=Depends(manager), db: Session = Depends(get_db)):
    return booking_valuation.preview(db, institute_id, appointment_id, request, user.get("sub"))
