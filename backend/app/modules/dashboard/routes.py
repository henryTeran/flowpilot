from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.modules.dashboard.schemas import InstituteDashboardRead
from app.modules.dashboard.service import get_institute_dashboard

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/institutes/{institute_id}/live", response_model=InstituteDashboardRead)
def get_live_institute_dashboard(
    institute_id: str,
    db: Session = Depends(get_db),
) -> InstituteDashboardRead:
    return get_institute_dashboard(db, institute_id)
