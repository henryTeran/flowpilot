from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.permissions import require_same_institute, require_ticket_manager
from app.database.session import get_db
from app.modules.dashboard.schemas import InstituteDashboardRead
from app.modules.dashboard.service import get_institute_dashboard

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/institutes/{institute_id}/live", response_model=InstituteDashboardRead)
def get_live_institute_dashboard(
    institute_id: str,
    current_user: dict[str, str | None] = Depends(require_ticket_manager),
    db: Session = Depends(get_db),
) -> InstituteDashboardRead:
    require_same_institute(current_user, institute_id)
    return get_institute_dashboard(db, institute_id)
