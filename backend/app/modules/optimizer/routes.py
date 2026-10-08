from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.permissions import require_ticket_manager
from app.database.session import get_db
from app.modules.optimizer import originals, sources
from app.modules.waitlist.originals import Envelope

router = APIRouter(prefix="/optimizer/institutes/{institute_id}", tags=["optimizer"])


def manager(institute_id: str, user=Depends(require_ticket_manager)):
    if user.get("institute_id") != institute_id or user.get("role") != "responsable_institut":
        raise HTTPException(403, "Permission insuffisante")
    return user


@router.post("/policy-originals", response_model=Envelope)
def create(institute_id: str, body: originals.Request, user=Depends(manager), db: Session = Depends(get_db)):
    return originals.create(db, institute_id, body, user.get("sub"))


@router.get("/policy-original-by-key", response_model=Envelope | None)
def recover(institute_id: str, key: str = Query(min_length=1, max_length=120), user=Depends(manager), db: Session = Depends(get_db)):
    return originals.by_key(db, institute_id, key)


@router.get("/policy-originals", response_model=originals.Audit)
def audit(institute_id: str, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=50), user=Depends(manager), db: Session = Depends(get_db)):
    return originals.audit(db, institute_id, offset, limit)


@router.get("/policy-originals/{identifier}", response_model=Envelope)
def detail(institute_id: str, identifier: str, user=Depends(manager), db: Session = Depends(get_db)):
    return originals.require(db, institute_id, identifier)


@router.post("/reviews/current", response_model=sources.Read)
def current(institute_id: str, body: sources.Request, user=Depends(manager), db: Session = Depends(get_db)):
    return sources.read(db, institute_id, body)
