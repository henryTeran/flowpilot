from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_serializer, model_validator
from app.modules.inventory.schemas import Quantity, Reason, ReplayKey
from app.shared.time import explicit_utc_instant

Identifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Reference = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")]


class OrderEntryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    item_id: Identifier
    unit: Literal["ml", "g", "unit"]
    quantity: Quantity = Field(gt=0)


class ReceiptCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entries: list[OrderEntryCreate] = Field(min_length=1, max_length=50)
    reason: Reason
    idempotency_key: ReplayKey

    @model_validator(mode="after")
    def unique_articles(self):
        if len({row.item_id for row in self.entries}) != len(self.entries):
            raise ValueError("Un article ne peut figurer qu'une fois")
        return self


class OrderCreate(ReceiptCreate):
    supplier_id: Identifier
    reference: Reference


class OrderEntryRead(BaseModel):
    item_id: str
    item_name: str
    item_sku: str
    unit: Literal["ml", "g", "unit"]
    quantity: Decimal

    @field_serializer("quantity")
    def exact(self, value):
        return format(value, ".3f")


class OrderRead(BaseModel):
    id: str
    institute_id: str
    supplier_id: str
    supplier_reference: str
    supplier_name: str
    reference: str
    reason: str
    actor_id: str
    idempotency_key: str
    created_at: datetime
    entries: list[OrderEntryRead] = Field(min_length=1, max_length=50)

    @field_serializer("created_at")
    def instant(self, value):
        return explicit_utc_instant(value)


class ReceiptEntryRead(BaseModel):
    item_id: str
    unit: Literal["ml", "g", "unit"]
    quantity: Decimal
    movement_id: str

    @field_serializer("quantity")
    def exact(self, value):
        return format(value, ".3f")


class ReceiptRead(BaseModel):
    id: str
    institute_id: str
    order_id: str
    reason: str
    actor_id: str
    idempotency_key: str
    occurred_at: datetime
    entries: list[ReceiptEntryRead] = Field(min_length=1, max_length=50)

    @field_serializer("occurred_at")
    def instant(self, value):
        return explicit_utc_instant(value)


class ProgressEntryRead(OrderEntryRead):
    received: Decimal
    remaining: Decimal

    @field_serializer("received", "remaining")
    def exact_progress(self, value):
        return format(value, ".3f")


class OrderProgressRead(BaseModel):
    institute_id: str
    order_id: str
    state: Literal["pending", "partial", "received"]
    entries: list[ProgressEntryRead] = Field(min_length=1, max_length=50)
