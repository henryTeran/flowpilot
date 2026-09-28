from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.services.models import Service, ServiceCategory


def list_categories(db: Session, limit: int | None = None, offset: int | None = None) -> list[ServiceCategory]:
    stmt = select(ServiceCategory).order_by(ServiceCategory.name)
    if limit is not None:
        stmt = stmt.limit(limit)
    if offset is not None:
        stmt = stmt.offset(offset)
    return list(db.scalars(stmt).all())


def list_services(
    db: Session,
    category_id: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> list[Service]:
    stmt = select(Service).where(Service.status == "active").order_by(Service.name)
    if category_id:
        stmt = stmt.where(Service.category_id == category_id)
    if limit is not None:
        stmt = stmt.limit(limit)
    if offset is not None:
        stmt = stmt.offset(offset)
    return list(db.scalars(stmt).all())


def get_service(db: Session, service_id: str) -> Service | None:
    return db.get(Service, service_id)


def save_service(db: Session, service: Service) -> Service:
    db.add(service)
    db.commit()
    db.refresh(service)
    return service
