from datetime import date, datetime, timezone
from typing import Annotated, Literal
from pydantic import AwareDatetime, BaseModel, ConfigDict, StringConstraints, field_validator, model_validator
from app.modules.resources.schemas import Code, Name
from app.modules.workforce.absence_schemas import Reason, Key
from app.modules.workforce.schemas import MatrixPage
from app.shared.time import explicit_utc_instant


class CertificationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    employee_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    code: Code
    title: Name
    issuer: Name
    reference: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
    issued_on: date | None
    valid_from: AwareDatetime
    valid_until: AwareDatetime | None
    reason: Reason
    idempotency_key: Key

    @model_validator(mode="after")
    def interval(self):
        try:
            self.valid_from = self.valid_from.astimezone(timezone.utc)
            if self.valid_until is not None:
                self.valid_until = self.valid_until.astimezone(timezone.utc)
        except OverflowError as error:
            raise ValueError("Instant hors des limites de la validite") from error
        if self.valid_until is not None:
            if self.valid_until <= self.valid_from:
                raise ValueError("La fin de validite doit suivre son debut")
        return self


class CertificationRevoke(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: Reason
    idempotency_key: Key


class RevocationRead(CertificationRevoke):
    model_config = ConfigDict(from_attributes=True)
    id: str
    institute_id: str
    certification_id: str
    actor_id: str
    created_at: AwareDatetime

    @field_validator("created_at", mode="before")
    @classmethod
    def aware(cls, value):
        return explicit_utc_instant(value) if isinstance(value, datetime) else value


class CertificationRead(CertificationCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    institute_id: str
    actor_id: str
    created_at: AwareDatetime
    revocation: RevocationRead | None = None

    @field_validator("valid_from", "valid_until", "created_at", mode="before")
    @classmethod
    def aware(cls, value):
        return explicit_utc_instant(value) if isinstance(value, datetime) else value


class CertificationState(BaseModel):
    certificate: CertificationRead
    state: Literal["not_yet_valid", "in_validity_window", "expired", "revoked"]


class CertificationPage(BaseModel):
    institute_id: str
    employee_id: str
    generated_at: AwareDatetime
    page: MatrixPage
    rows: list[CertificationState]
