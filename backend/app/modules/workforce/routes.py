from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.permissions import require_ticket_manager
from app.database.session import get_db
from app.modules.workforce.schemas import SkillMatrixRead
from app.modules.workforce.service import read_skill_matrix

router = APIRouter(prefix="/workforce/institutes/{institute_id}", tags=["workforce"])


@router.get("/skill-matrix", response_model=SkillMatrixRead)
def get_skill_matrix(
    institute_id: str,
    employee_offset: int = Query(0, ge=0, le=2147483647),
    employee_limit: int = Query(10, ge=1, le=25),
    service_offset: int = Query(0, ge=0, le=2147483647),
    service_limit: int = Query(10, ge=1, le=25),
    user: dict = Depends(require_ticket_manager),
    db: Session = Depends(get_db),
):
    if user.get("institute_id") != institute_id:
        raise HTTPException(status_code=403, detail="Institut non autorise")
    return read_skill_matrix(db, institute_id, employee_offset, employee_limit, service_offset, service_limit)
