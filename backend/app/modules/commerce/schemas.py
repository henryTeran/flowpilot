from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Identifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
ReplayKey = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class PackagePlanCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    service_id: Identifier
    sessions: int = Field(ge=1, le=1000, strict=True)
    valid_days: int = Field(ge=1, le=3650, strict=True)


class PackageIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan_id: Identifier
    customer_id: Identifier
    idempotency_key: ReplayKey


class PackageConsume(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticket_line_id: Identifier
    idempotency_key: ReplayKey


class PackagePlanRead(PackagePlanCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    institute_id: str


class PackageRead(BaseModel):
    id: str
    institute_id: str
    plan_id: str
    customer_id: str
    service_id: str
    name: str
    sessions: int
    consumed: int
    remaining: int
    usable_sessions: int
    status: str
    issued_at: datetime
    expires_at: datetime


class RedemptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    package_id: str
    ticket_line_id: str
    sessions: int
    original_unit_price: float | None
    original_total: float | None
    occurred_at: datetime
    actor_id: str | None
