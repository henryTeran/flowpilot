from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.permissions import require_same_institute, require_ticket_manager
from app.database.session import get_db
from app.modules.institutes.repository import get_institute, list_institutes
from app.modules.institutes.schemas import InstituteRead
from app.shared.exceptions import not_found
from app.shared.pagination import PaginationParams, pagination_params

router = APIRouter(prefix="/institutes", tags=["institutes"])


@router.get("", response_model=list[InstituteRead])
def get_accessible_institutes(
    pagination: PaginationParams = Depends(pagination_params),
    current_user: dict[str, str | None] = Depends(require_ticket_manager),
    db: Session = Depends(get_db),
) -> list[InstituteRead]:
    if current_user.get("institute_id"):
        institute = get_institute(db, current_user["institute_id"])
        if not institute:
            return []
        return [institute]

    return list_institutes(db, limit=pagination.limit, offset=pagination.offset)


@router.get("/{institute_id}", response_model=InstituteRead)
def get_institute_detail(
    institute_id: str,
    current_user: dict[str, str | None] = Depends(require_ticket_manager),
    db: Session = Depends(get_db),
) -> InstituteRead:
    require_same_institute(current_user, institute_id)
    institute = get_institute(db, institute_id)
    if not institute:
        raise not_found("Institut introuvable")
    return institute
