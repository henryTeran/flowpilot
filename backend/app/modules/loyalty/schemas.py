from datetime import datetime
from decimal import Decimal
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

ReplayKey = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=240)]


class AdjustmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    points: int = Field(strict=True, ge=-1_000_000_000, le=1_000_000_000)
    reason: Reason
    idempotency_key: ReplayKey


class TierCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    minimum_points: int = Field(strict=True, ge=0, le=1_000_000_000)
    benefit_description: Reason
    idempotency_key: ReplayKey


class EntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    points: int
    reason: str
    actor_id: str
    occurred_at: datetime


class TierRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    minimum_points: int
    benefit_description: str


class BalanceRead(BaseModel):
    customer_id: str
    points: int
    tier: TierRead | None


class EarningPolicyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    currency: Annotated[str, StringConstraints(pattern=r"^(CHF|EUR)$")]
    points_per_unit: Decimal = Field(gt=0, le=10000, max_digits=9, decimal_places=4)
    enabled: bool = Field(strict=True)
    reason: Reason
    idempotency_key: ReplayKey


class EarningPolicyRead(EarningPolicyCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    revision: int
    actor_id: str
    created_at: datetime


class EarningRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    ticket_id: str
    policy_id: str
    currency: str
    basis_amount: Decimal
    points_per_unit: Decimal
    points: int
    actor_id: str
    occurred_at: datetime


class RewardCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    service_id: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    points_cost: int = Field(strict=True, gt=0, le=1_000_000_000)
    minimum_points: int = Field(strict=True, ge=0, le=1_000_000_000)
    discount_amount: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    currency: Annotated[str, StringConstraints(pattern=r"^(CHF|EUR)$")]
    idempotency_key: ReplayKey


class RewardRead(RewardCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    actor_id: str
    created_at: datetime


class RewardApply(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticket_line_id: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    idempotency_key: ReplayKey


class RewardReverse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: Reason


class RedemptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    customer_id: str
    reward_id: str
    ticket_line_id: str
    quantity: int
    points_cost: int
    currency: str
    original_unit_price: Decimal
    original_total: Decimal
    reward_unit_price: Decimal
    reward_total: Decimal
    actor_id: str
    occurred_at: datetime
    reversed_at: datetime | None
    reversed_by: str | None
    reversal_reason: str | None


class CustomerSnapshot(BaseModel):
    balance: BalanceRead
    entries: list[EntryRead]
    redemptions: list[RedemptionRead]
