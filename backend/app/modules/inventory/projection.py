"""Exact time and quantity primitives for source-backed stock projections.

No demand inference or stock writes. Callers must establish source coverage
before presenting a projected quantity as a complete estimate.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal


def utc_instant(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Explicit timezone required")
    return value.astimezone(timezone.utc)


def microseconds(duration: timedelta) -> int:
    return ((duration.days * 86400 + duration.seconds) * 1000000
            + duration.microseconds)


@dataclass(frozen=True)
class ProjectionWindow:
    requested_start: datetime
    effective_start: datetime
    end: datetime
    observed_start: datetime
    observed_end: datetime
    generated_at: datetime

    @classmethod
    def create(cls, starts_at: datetime, ends_at: datetime,
               observed_starts_at: datetime, observed_ends_at: datetime,
               now: datetime) -> "ProjectionWindow":
        start, end, observed_start, observed_end, generated = map(
            utc_instant, (starts_at, ends_at, observed_starts_at, observed_ends_at, now))
        maximum = timedelta(days=366)
        if not timedelta(0) < end - start <= maximum:
            raise ValueError("Future horizon must be positive and at most 366 days")
        if not timedelta(0) < observed_end - observed_start <= maximum:
            raise ValueError("Observed window must be positive and at most 366 days")
        effective = max(start, generated)
        if end <= effective:
            raise ValueError("Future horizon has already ended")
        if observed_end > generated or observed_end > effective:
            raise ValueError("Observed window must end before the projection")
        return cls(start, effective, end, observed_start, observed_end, generated)

    def observed(self, completed_at: datetime) -> bool:
        # Completion, not the potentially much later stock confirmation time.
        return self.observed_start <= utc_instant(completed_at) < self.observed_end

    def project(self, measured_milli: int, unit: Literal["ml", "g", "unit"]) -> int:
        if type(measured_milli) is not int or measured_milli < 0:
            raise ValueError("Measured quantity must be a nonnegative integer")
        if unit not in ("ml", "g", "unit"):
            raise ValueError("Unknown stock unit")
        quantum = 1000 if unit == "unit" else 1
        if measured_milli % quantum:
            raise ValueError("Measured whole-unit quantity is fractional")
        numerator = measured_milli * microseconds(self.end - self.effective_start)
        denominator = microseconds(self.observed_end - self.observed_start) * quantum
        return ((numerator + denominator - 1) // denominator) * quantum
