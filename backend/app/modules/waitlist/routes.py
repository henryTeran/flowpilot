from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.permissions import require_ticket_manager
from app.database.session import get_db
from app.modules.waitlist import originals

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
