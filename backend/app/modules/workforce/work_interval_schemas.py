from datetime import datetime, timezone
import re
from typing import Annotated
from pydantic import AwareDatetime, BaseModel, ConfigDict, StringConstraints, model_validator, field_validator
from app.modules.workforce.absence_schemas import Reason, Key, AbsenceCancel
from app.modules.workforce.schemas import MatrixPage
from app.shared.time import explicit_utc_instant


class WorkIntervalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    employee_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    start_time: AwareDatetime
    end_time: AwareDatetime
    reason: Reason
    idempotency_key: Key

    @field_validator("start_time", "end_time", mode="before")
    @classmethod
    def explicit_instant(cls, value):
        if not isinstance(value, datetime) and not (isinstance(value, str) and re.search(r"(?:Z|[+-]\d{2}:\d{2})$", value)):
            raise ValueError("Un instant avec fuseau explicite est requis")
        return value

    @model_validator(mode="after")
    def interval(self):
        try:
            self.start_time = self.start_time.astimezone(timezone.utc)
            self.end_time = self.end_time.astimezone(timezone.utc)
        except OverflowError as error:
            raise ValueError("Instant hors des limites supportees") from error
        if self.end_time <= self.start_time:
            raise ValueError("La fin effective doit suivre le debut effectif")
        return self


class WorkIntervalCancellationRead(AbsenceCancel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    institute_id: str
    work_interval_id: str
    actor_id: str
    created_at: AwareDatetime

    @field_validator("created_at", mode="before")
    @classmethod
    def aware(cls, value):
        return explicit_utc_instant(value) if isinstance(value, datetime) else value


class WorkIntervalRead(WorkIntervalCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    institute_id: str
    actor_id: str
    created_at: AwareDatetime
    cancellation: WorkIntervalCancellationRead | None = None

    @field_validator("start_time", "end_time", "created_at", mode="before")
    @classmethod
    def aware(cls, value):
        return explicit_utc_instant(value) if isinstance(value, datetime) else value


class WorkIntervalPage(BaseModel):
    institute_id: str
    employee_id: str
    generated_at: AwareDatetime
    page: MatrixPage
    rows: list[WorkIntervalRead]
