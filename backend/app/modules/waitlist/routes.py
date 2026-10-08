from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Literal
from app.core.permissions import require_ticket_manager
from app.database.session import get_db
from app.modules.waitlist import originals
from app.modules.waitlist import lifecycle
from app.modules.waitlist import sources

router = APIRouter(prefix="/waitlist/institutes/{institute_id}", tags=["waitlist"])


def manager(institute_id: str, user=Depends(require_ticket_manager)):
    if user.get("institute_id") != institute_id or user.get("role") != "responsable_institut":
        raise HTTPException(403, "Permission insuffisante")
    return user


@router.post("/originals", response_model=originals.Envelope)
def create(institute_id: str, request: originals.Request, user=Depends(manager), db: Session = Depends(get_db)):
    return originals.create(db, institute_id, request, user.get("sub"))


@router.get("/original-by-key", response_model=originals.Envelope | None)
def recover(institute_id: str, key: str = Query(min_length=1, max_length=120), user=Depends(manager), db: Session = Depends(get_db)):
    return originals.by_key(db, institute_id, key)


@router.get("/originals", response_model=originals.Audit)
def audit(institute_id: str, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=50),
        user=Depends(manager), db: Session = Depends(get_db)):
    return originals.audit(db, institute_id, offset, limit)


@router.get("/originals/{original_id}", response_model=originals.Envelope)
def original(institute_id: str, original_id: str, user=Depends(manager), db: Session = Depends(get_db)):
    return originals.require(db, institute_id, original_id)


@router.post("/lifecycle/originals", response_model=originals.Envelope)
def transition(institute_id: str, request: lifecycle.Request, user=Depends(manager), db: Session = Depends(get_db)):
    return lifecycle.create(db, institute_id, request, user.get("sub"))


@router.get("/lifecycle/original-by-key", response_model=originals.Envelope | None)
def recover_transition(institute_id: str, key: str = Query(min_length=1, max_length=120), user=Depends(manager), db: Session = Depends(get_db)):
    return lifecycle.by_key(db, institute_id, key)


@router.get("/lifecycle", response_model=lifecycle.Audit)
def lifecycle_audit(institute_id: str, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=50),
        user=Depends(manager), db: Session = Depends(get_db)):
    return lifecycle.audit(db, institute_id, offset, limit)


@router.get("/lifecycle/originals/{event_id}", response_model=originals.Envelope)
def lifecycle_event(institute_id: str, event_id: str, user=Depends(manager), db: Session = Depends(get_db)):
    return lifecycle.require(db, institute_id, event_id)


@router.get("/lifecycle/states/{root_id}", response_model=lifecycle.State)
def waitlist_state(institute_id: str, root_id: str, user=Depends(manager), db: Session = Depends(get_db)):
    return lifecycle.read_state(db, institute_id, root_id)


@router.get("/lifecycle/states/{root_id}/matching", response_model=sources.Read)
def matching(institute_id: str, root_id: str, horizon_end: sources.Horizon, channel: Literal["email", "sms"],
        history_requirement: Literal["review_only", "observed_care_required", "no_recorded_care_required"],
        permission_requirement: Literal["review_only", "recorded_grant_required"],
        expected_event_id: str = Query(min_length=1, max_length=80),
        expected_event_fingerprint: str = Query(pattern=r"^[0-9a-f]{64}$"),
        user=Depends(manager), db: Session = Depends(get_db)):
    policy = sources.Policy(channel=channel, history_requirement=history_requirement, permission_requirement=permission_requirement)
    return sources.read(db, institute_id, root_id, expected_event_id, expected_event_fingerprint, horizon_end, policy)
