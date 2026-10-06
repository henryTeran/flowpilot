"""Read-only, explicitly scoped service-volume scenarios; no inferred demand."""
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_serializer, model_validator
from app.shared.time import explicit_utc_instant

Identifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class ScenarioDemand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    service_id: Identifier
    quantity: int = Field(strict=True, ge=1, le=100000)
    recipe_id: Identifier | None  # Explicitly missing, never silently use today's recipe.


class ForecastScenario(BaseModel):
    model_config = ConfigDict(extra="forbid")
    starts_at: datetime
    ends_at: datetime
    demands: list[ScenarioDemand] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def explicit_scope(self):
        if any(value.tzinfo is None or value.utcoffset() is None for value in (self.starts_at, self.ends_at)):
            raise ValueError("Instants avec fuseau requis")
        self.starts_at = self.starts_at.astimezone(timezone.utc)
        self.ends_at = self.ends_at.astimezone(timezone.utc)
        if not timedelta(0) < self.ends_at - self.starts_at <= timedelta(days=366):
            raise ValueError("Horizon positif limite a 366 jours")
        if len({row.service_id for row in self.demands}) != len(self.demands):
            raise ValueError("Une prestation ne peut figurer qu'une fois")
        return self


class DemandRead(ScenarioDemand):
    service_name: str
    recipe_revision: int | None
    state: Literal["enabled", "disabled", "missing_selected_norm"]


class OutlookItem(BaseModel):
    item_id: str
    item_sku: str
    item_name: str
    category: Literal["retail", "cabine", "consumable"]
    unit: Literal["ml", "g", "unit"]
    on_hand: str
    threshold: str
    at_or_below_threshold: bool
    threshold_shortfall: str
    pending_order_quantity: str
    known_demand: str
    complete_demand: str | None
    known_demand_shortfall: str
    conditional_shortfall_after_all_orders: str


class OutlookRead(BaseModel):
    institute_id: str
    generated_at: datetime
    starts_at: datetime | None
    ends_at: datetime | None
    source: Literal["recorded_stock", "explicit_service_volume_scenario"]
    coverage: Literal["not_applicable", "complete_selected_norms", "partial_selected_norms"]
    demands: list[DemandRead]
    limit: int
    offset: int
    items: list[OutlookItem]

    @field_serializer("generated_at", "starts_at", "ends_at")
    def instant(self, value):
        return explicit_utc_instant(value) if value is not None else None
