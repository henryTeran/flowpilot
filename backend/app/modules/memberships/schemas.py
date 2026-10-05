from datetime import datetime
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Identifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
ReplayKey = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class PlanCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    valid_days: int = Field(ge=1, le=3650, strict=True)
    idempotency_key: ReplayKey


class MembershipIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan_id: Identifier
    customer_id: Identifier
    idempotency_key: ReplayKey


class MembershipRenew(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idempotency_key: ReplayKey


class PlanRead(PlanCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    institute_id: str
    actor_id: str | None


class MembershipRead(BaseModel):
    id: str
    institute_id: str
    plan_id: str
    customer_id: str
    name: str
    valid_days: int
    issued_at: datetime
    active_from: datetime
    active_until: datetime
    status: str


class RenewalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    membership_id: str
    previous_from: datetime
    previous_until: datetime
    active_from: datetime
    active_until: datetime
    occurred_at: datetime
    actor_id: str | None
