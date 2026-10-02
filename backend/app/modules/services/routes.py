from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.permissions import require_ticket_manager
from app.database.session import get_db
from app.modules.services.repository import list_categories, list_services
from app.modules.services.schemas import ServiceCategoryRead, ServiceCreate, ServiceRead
from app.modules.services.service import create_service
from app.shared.pagination import PaginationParams, pagination_params

router = APIRouter(prefix="/services", tags=["services"])


@router.get("/categories", response_model=list[ServiceCategoryRead])
def get_categories(
    pagination: PaginationParams = Depends(pagination_params),
    db: Session = Depends(get_db),
) -> list[ServiceCategoryRead]:
    return list_categories(db, limit=pagination.limit, offset=pagination.offset)


@router.get("/catalog", response_model=list[ServiceRead])
def get_catalog(
    category_id: str | None = None,
    pagination: PaginationParams = Depends(pagination_params),
    db: Session = Depends(get_db),
) -> list[ServiceRead]:
    return list_services(db, category_id=category_id, limit=pagination.limit, offset=pagination.offset)


@router.post("", response_model=ServiceRead)
def post_service(
    payload: ServiceCreate,
    _: dict[str, str | None] = Depends(require_ticket_manager),
    db: Session = Depends(get_db),
) -> ServiceRead:
    return create_service(db, payload)
