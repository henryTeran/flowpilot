from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Currency = Literal["CHF", "EUR"]
Identifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
ReplayKey = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class SettingsWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    currency: Currency


class SettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    currency: Currency
    updated_at: datetime
    actor_id: str


class GiftCardIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")
    amount: Decimal = Field(gt=0, max_digits=10, decimal_places=2, le=Decimal("99999999.99"))
    valid_days: int = Field(ge=1, le=3650, strict=True)
    customer_id: Identifier | None = None
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=240)]
    idempotency_key: ReplayKey


class GiftCardLookup(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=20, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")]


class GiftCardRead(BaseModel):
    id: str
    institute_id: str
    currency: Currency
    initial_amount: Decimal
    remaining: Decimal
    usable_amount: Decimal
    customer_id: str | None
    issued_at: datetime
    expires_at: datetime
    status: str


class GiftCardIssueRead(GiftCardRead):
    code: str
