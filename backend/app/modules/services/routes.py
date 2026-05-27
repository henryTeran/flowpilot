from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.modules.services.repository import list_categories, list_services
from app.modules.services.schemas import ServiceCategoryRead, ServiceCreate, ServiceRead
from app.modules.services.service import create_service

router = APIRouter(prefix="/services", tags=["services"])


@router.get("/categories", response_model=list[ServiceCategoryRead])
def get_categories(db: Session = Depends(get_db)) -> list[ServiceCategoryRead]:
    return list_categories(db)


@router.get("/catalog", response_model=list[ServiceRead])
def get_catalog(category_id: str | None = None, db: Session = Depends(get_db)) -> list[ServiceRead]:
    return list_services(db, category_id=category_id)


@router.post("", response_model=ServiceRead)
def post_service(payload: ServiceCreate, db: Session = Depends(get_db)) -> ServiceRead:
    return create_service(db, payload)
