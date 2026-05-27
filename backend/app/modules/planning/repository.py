from datetime import datetime, time, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.planning.models import ServiceSession


def list_sessions_for_day(db: Session, institute_id: str, day: datetime) -> list[ServiceSession]:
    start = datetime.combine(day.date(), time.min, tzinfo=timezone.utc)
    end = datetime.combine(day.date(), time.max, tzinfo=timezone.utc)
    return list(
        db.scalars(
            select(ServiceSession)
            .where(
                ServiceSession.institute_id == institute_id,
                ServiceSession.start_time >= start,
                ServiceSession.start_time <= end,
            )
            .order_by(ServiceSession.start_time)
        ).all()
    )


def get_session(db: Session, session_id: str) -> ServiceSession | None:
    return db.get(ServiceSession, session_id)


def save_session(db: Session, session: ServiceSession) -> ServiceSession:
    db.add(session)
    db.commit()
    db.refresh(session)
    return session
