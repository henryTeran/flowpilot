from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.institutes.models import Institute


def list_institutes(db: Session) -> list[Institute]:
    return list(db.scalars(select(Institute).order_by(Institute.city, Institute.name)).all())


def get_institute(db: Session, institute_id: str) -> Institute | None:
    return db.get(Institute, institute_id)
