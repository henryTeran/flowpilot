from fastapi import APIRouter, Depends, HTTPException
from pydantic import AwareDatetime
from sqlalchemy.orm import Session
from app.core.permissions import require_ticket_manager
from app.database.session import get_db
from app.modules.revenue import billing, sources

router = APIRouter(prefix="/revenue/institutes/{institute_id}", tags=["revenue"])


def manager(institute_id: str, user=Depends(require_ticket_manager)):
    if user.get("institute_id") != institute_id or user.get("role") != "responsable_institut":
        raise HTTPException(403, "Permission insuffisante")
    return user


@router.get("/billing", response_model=billing.Billing)
def recorded_billing(institute_id: str, start: AwareDatetime, end: AwareDatetime,
    user=Depends(manager), db: Session = Depends(get_db)):
    return sources.read(db, institute_id, start, end)
