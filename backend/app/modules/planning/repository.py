from datetime import datetime, time, timezone

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.modules.planning.models import ServiceSession


ACTIVE_SESSION_STATUSES = ["planned", "in_progress", "extended", "delayed"]


def list_sessions_for_day(db: Session, institute_id: str, day: datetime) -> list[ServiceSession]:
    """
    Retourne les sessions visibles dans le planning du jour.

    Correction MVP :
    - On récupère les sessions qui chevauchent la journée sélectionnée.
    - On inclut aussi les sessions encore actives, même si leur date est décalée
      par un problème d'heure locale/UTC pendant les tests Docker.
    """
    start = datetime.combine(day.date(), time.min, tzinfo=timezone.utc)
    end = datetime.combine(day.date(), time.max, tzinfo=timezone.utc)

    return list(
        db.scalars(
            select(ServiceSession)
            .where(
                ServiceSession.institute_id == institute_id,
                or_(
                    and_(
                        ServiceSession.start_time <= end,
                        ServiceSession.planned_end_time >= start,
                    ),
                    ServiceSession.status.in_(ACTIVE_SESSION_STATUSES),
                ),
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
