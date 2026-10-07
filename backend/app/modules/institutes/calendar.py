from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from app.modules.institutes.models import Institute
from app.shared.exceptions import business_error, not_found


def day_bounds(db: Session, institute_id: str, day: date | datetime) -> tuple[datetime, datetime]:
    """Half-open UTC bounds of an institute civil day, including DST changes.

    A datetime selects the local day containing that instant; a date is an
    explicit civil date. Legacy invalid zone names use the UI's UTC fallback.
    """
    institute = db.get(Institute, institute_id)
    if institute is None:
        raise not_found("Institut introuvable")
    try:
        zone = ZoneInfo(institute.timezone)
    except (ZoneInfoNotFoundError, ValueError):
        zone = timezone.utc
    if isinstance(day, datetime):
        instant = day if day.tzinfo is not None else day.replace(tzinfo=timezone.utc)
        civil = instant.astimezone(zone).date()
    else:
        civil = day
    try:
        return (datetime.combine(civil, time.min, zone).astimezone(timezone.utc),
                datetime.combine(civil + timedelta(days=1), time.min, zone).astimezone(timezone.utc))
    except OverflowError as error:
        raise business_error("Date hors des limites du calendrier") from error
