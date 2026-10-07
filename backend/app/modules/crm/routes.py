from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.permissions import require_ticket_manager
from app.database.session import get_db
from app.modules.crm import policies
from app.modules.crm import profile
from app.modules.crm import return_sources

router = APIRouter(prefix="/crm/institutes/{institute_id}", tags=["crm"])


def manager(institute_id: str, user=Depends(require_ticket_manager)):
    if user.get("institute_id") != institute_id or user.get("role") != "responsable_institut":
        raise HTTPException(403, "Permission insuffisante")
    return user


@router.get("/customers/{customer_id}/segment", response_model=profile.SegmentProfile)
def segment(institute_id: str, customer_id: str, user=Depends(manager), db: Session = Depends(get_db)):
    return profile.read(db, institute_id, customer_id)


@router.get("/customers/{customer_id}/return-cycle", response_model=return_sources.ReturnRead)
def return_cycle(institute_id: str, customer_id: str,
                 start: str = Query(min_length=1, max_length=64), end: str = Query(min_length=1, max_length=64),
                 limit: int = Query(default=20, ge=1, le=50), offset: int = Query(default=0, ge=0),
                 user=Depends(manager), db: Session = Depends(get_db)):
    return return_sources.read(db, institute_id, customer_id, start, end, limit, offset)


@router.post("/segment-policies", response_model=policies.PolicyRead)
def create(institute_id: str, payload: policies.PolicyCreate, user=Depends(manager), db: Session = Depends(get_db)):
    return policies.create(db, institute_id, payload, user.get("sub"))


@router.get("/segment-policies/current", response_model=policies.PolicyRead | None)
def current(institute_id: str, user=Depends(manager), db: Session = Depends(get_db)):
    return policies.current(db, institute_id)


@router.get("/segment-policies/original/{key}", response_model=policies.PolicyRead | None)
def original(institute_id: str, key: str, user=Depends(manager), db: Session = Depends(get_db)):
    return policies.original(db, institute_id, key)


@router.get("/segment-policies/{identifier}", response_model=policies.PolicyRead)
def detail(institute_id: str, identifier: str, user=Depends(manager), db: Session = Depends(get_db)):
    return policies.require(db, institute_id, identifier)
