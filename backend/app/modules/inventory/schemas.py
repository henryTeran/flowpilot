from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_serializer
from app.shared.time import explicit_utc_instant

MAX_QUANTITY = Decimal("999999999999.999")
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=240)]
ReplayKey = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Quantity = Annotated[Decimal, Field(max_digits=15, decimal_places=3, ge=-MAX_QUANTITY, le=MAX_QUANTITY)]


class ItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sku: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")]
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    category: Literal["retail", "cabine", "consumable"]
    unit: Literal["ml", "g", "unit"]
    reorder_threshold: Quantity = Field(ge=0)
    reason: Reason
    idempotency_key: ReplayKey


class MovementCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["receipt", "adjustment"]
    quantity: Quantity
    reason: Reason
    idempotency_key: ReplayKey


class ItemRead(BaseModel):
    id: str
    institute_id: str
    sku: str
    name: str
    category: str
    unit: str
    reorder_threshold: Decimal
    on_hand: Decimal
    at_or_below_threshold: bool
    actor_id: str
    created_at: datetime

    @field_serializer("reorder_threshold", "on_hand")
    def quantity_string(self, value):
        return format(value, ".3f")

    @field_serializer("created_at")
    def timestamp(self, value):
        return explicit_utc_instant(value)


class MovementRead(BaseModel):
    id: str
    institute_id: str
    item_id: str
    kind: str
    quantity: Decimal
    unit: str
    reason: str
    actor_id: str
    idempotency_key: str
    occurred_at: datetime

    @field_serializer("quantity")
    def quantity_string(self, value):
        return format(value, ".3f")

    @field_serializer("occurred_at")
    def timestamp(self, value):
        return explicit_utc_instant(value)
