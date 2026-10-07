from datetime import date, datetime
import re
from typing import Annotated, Literal
from pydantic import StrictInt, AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, model_validator, field_validator
from app.modules.workforce.absence_schemas import Reason, Key
from app.shared.time import explicit_utc_instant
from app.modules.workforce.schemas import MatrixPage
from app.modules.workforce.commission_sources import CommissionTerms


class CommissionRuleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    employee_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    basis: Literal["closed_attributed_line_gross"]
    currency: Literal["CHF", "EUR"]
    category: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
    service_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)] | None
    rate_basis_points: StrictInt = Field(ge=0, le=10000)
    rounding: Literal["half_up", "half_even", "down"]
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

    @model_validator(mode="after")
    def terms(self):
        if self.last_day < self.first_day:
            raise ValueError("Le dernier jour doit suivre ou egaler le premier")
        return self


class CommissionRuleCancel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: Reason
    idempotency_key: Key


class CancellationRead(CommissionRuleCancel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    institute_id: str
    rule_id: str
    actor_id: str
    created_at: AwareDatetime

    @field_validator("created_at", mode="before")
    @classmethod
    def aware(cls, value):
        return explicit_utc_instant(value) if isinstance(value, datetime) else value


class CommissionRuleRead(CommissionRuleCreate):
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


class CommissionRulePage(BaseModel):
    institute_id: str
    employee_id: str
    generated_at: AwareDatetime
    page: MatrixPage
    rows: list[CommissionRuleRead]


def calculation_terms(original: CommissionRuleRead):
    return CommissionTerms.model_validate(original.model_dump(include=set(CommissionTerms.model_fields)))
