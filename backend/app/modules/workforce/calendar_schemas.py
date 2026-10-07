from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, AwareDatetime, field_validator
from app.modules.workforce.schemas import MatrixEmployee, MatrixPage
from app.modules.scheduling.models import AvailabilityResult
from app.shared.time import explicit_utc_instant


class EmployeeCalendarEvent(BaseModel):
    source_kind: Literal["appointment", "session", "absence"]
    id: str
    status: str
    service_id: str | None
    service_name: str | None
    start_time: AwareDatetime
    end_time: AwareDatetime
    actual_start_time: AwareDatetime | None
    actual_end_time: AwareDatetime | None
    absence_kind: Literal["absence", "leave"] | None
    reason: str | None
    cancellation_id: str | None

    @field_validator("start_time", "end_time", "actual_start_time", "actual_end_time", mode="before")
    @classmethod
    def restore_utc(cls, value):
        return explicit_utc_instant(value) if isinstance(value, datetime) else value


class EmployeeDayRead(BaseModel):
    institute_id: str
    generated_at: AwareDatetime
    employee: MatrixEmployee
    day: date
    timezone: str
    day_start: AwareDatetime
    day_end: AwareDatetime
    availability: AvailabilityResult
    event_page: MatrixPage
    events: list[EmployeeCalendarEvent]
