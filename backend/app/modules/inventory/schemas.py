from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_serializer, model_validator
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


class RecipeEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    item_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    quantity: Quantity = Field(gt=0)


class RecipeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base_revision: int = Field(ge=0, lt=1000000000, strict=True)
    enabled: bool = Field(strict=True)
    entries: list[RecipeEntry] = Field(max_length=50)
    reason: Reason
    idempotency_key: ReplayKey

    @model_validator(mode="after")
    def coherent_entries(self):
        if self.enabled != bool(self.entries):
            raise ValueError("Une recette active exige des articles; une desactivation exige une liste vide")
        if len({entry.item_id for entry in self.entries}) != len(self.entries):
            raise ValueError("Chaque article doit apparaitre une seule fois")
        return self


class RecipeEntryRead(BaseModel):
    item_id: str
    quantity: Decimal
    unit: Literal["ml", "g", "unit"]

    @field_serializer("quantity")
    def quantity_string(self, value):
        return format(value, ".3f")


class RecipeRead(BaseModel):
    id: str
    institute_id: str
    service_id: str
    revision: int
    base_revision: int
    enabled: bool
    entries: list[RecipeEntryRead]
    reason: str
    actor_id: str
    idempotency_key: str
    created_at: datetime

    @field_serializer("created_at")
    def timestamp(self, value):
        return explicit_utc_instant(value)


class ServiceBasisEntryRead(BaseModel):
    id: str
    ticket_line_id: str | None
    service_id: str
    quantity: int
    state: Literal["enabled", "disabled", "unconfigured"]
    actor_id: str | None
    captured_at: datetime
    recipe: RecipeRead | None

    @field_serializer("captured_at")
    def timestamp(self, value):
        return explicit_utc_instant(value)


class ServiceBasisRead(BaseModel):
    institute_id: str
    source_kind: Literal["sessions", "appointments"]
    source_id: str
    captured: bool
    entries: list[ServiceBasisEntryRead]
