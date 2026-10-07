from datetime import datetime, timezone
from typing import Annotated, Literal
from pydantic import AwareDatetime, BaseModel, ConfigDict, StringConstraints, model_validator, field_validator
from app.shared.time import explicit_utc_instant

Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=240)]
Key = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class AbsenceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    employee_id: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    kind: Literal["absence", "leave"]
    start_time: AwareDatetime
    end_time: AwareDatetime
    reason: Reason
    idempotency_key: Key

    @model_validator(mode="after")
    def interval(self):
        self.start_time = self.start_time.astimezone(timezone.utc)
        self.end_time = self.end_time.astimezone(timezone.utc)
        if self.end_time <= self.start_time:
            raise ValueError("La fin doit suivre le debut de l'absence")
        return self


class AbsenceCancel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: Reason
    idempotency_key: Key


class CancellationRead(AbsenceCancel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    institute_id: str
    absence_id: str
    actor_id: str
    created_at: datetime

    @field_validator("created_at", mode="before")
    @classmethod
    def aware(cls, value):
        return explicit_utc_instant(value) if isinstance(value, datetime) else value


class AbsenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    institute_id: str
    employee_id: str
    kind: Literal["absence", "leave"]
    start_time: datetime
    end_time: datetime
    reason: str
    actor_id: str
    idempotency_key: str
    created_at: datetime
    cancellation: CancellationRead | None = None

    @field_validator("start_time", "end_time", "created_at", mode="before")
    @classmethod
    def aware(cls, value):
        return explicit_utc_instant(value) if isinstance(value, datetime) else value
