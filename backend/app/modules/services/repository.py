from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.services.models import Service, ServiceCategory


def list_categories(db: Session) -> list[ServiceCategory]:
    return list(db.scalars(select(ServiceCategory).order_by(ServiceCategory.name)).all())


def list_services(db: Session, category_id: str | None = None) -> list[Service]:
    stmt = select(Service).where(Service.status == "active").order_by(Service.name)
    if category_id:
        stmt = stmt.where(Service.category_id == category_id)
    return list(db.scalars(stmt).all())


def get_service(db: Session, service_id: str) -> Service | None:
    return db.get(Service, service_id)


def save_service(db: Session, service: Service) -> Service:
    db.add(service)
    db.commit()
    db.refresh(service)
    return service
