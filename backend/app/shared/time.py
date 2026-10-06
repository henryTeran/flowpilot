from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def explicit_utc_instant(value: datetime | None) -> datetime | None:
    """Restore UTC metadata dropped by SQLite for stored domain UTC instants."""
    return value.replace(tzinfo=timezone.utc) if value is not None and value.tzinfo is None else value
