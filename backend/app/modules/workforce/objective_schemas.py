from datetime import date, datetime
from decimal import Decimal
import re
from typing import Annotated, Literal
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, model_validator, field_validator
from app.modules.workforce.absence_schemas import Reason, Key
from app.shared.time import explicit_utc_instant
from app.modules.workforce.schemas import MatrixPage


class ObjectiveCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    employee_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    metric: Literal["closed_attributed_gross", "completed_sessions"]
    currency: Literal["CHF", "EUR"] | None
    target: Decimal = Field(gt=0, max_digits=20, decimal_places=2)
    first_day: date
    last_day: date
    reason: Reason
    idempotency_key: Key

    @field_validator("first_day", "last_day", mode="before")
    @classmethod
    def civil_date(cls, value):
        if isinstance(value, datetime) or not (isinstance(value, date) or isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)):
            raise ValueError("Une date civile YYYY-MM-DD est requise")
        return value

    @field_validator("target", mode="before")
    @classmethod
    def exact_target(cls, value):
        if isinstance(value, (float, bool)):
            raise ValueError("Utilisez une chaine decimale exacte pour la cible")
        return value

    @model_validator(mode="after")
    def terms(self):
        if self.last_day < self.first_day:
            raise ValueError("Le dernier jour doit suivre ou egaler le premier")
        if self.metric == "completed_sessions":
            if self.currency is not None or self.target != self.target.to_integral_value():
                raise ValueError("Les prestations terminees requierent une cible entiere sans devise")
        elif self.currency is None:
            raise ValueError("La cible monetaire requiert une devise explicite")
        return self


class ObjectiveCancel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: Reason
    idempotency_key: Key


class CancellationRead(ObjectiveCancel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    institute_id: str
    objective_id: str
    actor_id: str
    created_at: AwareDatetime

    @field_validator("created_at", mode="before")
    @classmethod
    def aware(cls, value):
        return explicit_utc_instant(value) if isinstance(value, datetime) else value


class ObjectiveRead(ObjectiveCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    institute_id: str
    timezone: str
    period_start: AwareDatetime
    period_end: AwareDatetime
    actor_id: str
    created_at: AwareDatetime
    cancellation: CancellationRead | None = None

    @field_validator("period_start", "period_end", "created_at", mode="before")
    @classmethod
    def aware(cls, value):
        return explicit_utc_instant(value) if isinstance(value, datetime) else value


class ObjectiveProgress(BaseModel):
    objective: ObjectiveRead
    period_state: Literal["upcoming", "active", "ended", "cancelled"]
    known_value: Decimal | None
    value: Decimal | None
    achieved: bool | None
    source_count: int | None
    missing_amount_sources: int | None
    unknown_currency_sources: int | None
    other_currency_sources: int | None


class ObjectivePage(BaseModel):
    institute_id: str
    employee_id: str
    generated_at: AwareDatetime
    page: MatrixPage
    rows: list[ObjectiveProgress]
