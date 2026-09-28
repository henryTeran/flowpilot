from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.institutes.models import Institute


def list_institutes(db: Session, limit: int | None = None, offset: int | None = None) -> list[Institute]:
    stmt = select(Institute).order_by(Institute.city, Institute.name)
    if limit is not None:
        stmt = stmt.limit(limit)
    if offset is not None:
        stmt = stmt.offset(offset)
    return list(db.scalars(stmt).all())


def get_institute(db: Session, institute_id: str) -> Institute | None:
    return db.get(Institute, institute_id)
