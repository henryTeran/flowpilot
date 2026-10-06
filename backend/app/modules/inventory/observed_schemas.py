from datetime import datetime, timedelta
from typing import Literal
from pydantic import BaseModel, ConfigDict, model_validator, field_serializer
from app.modules.inventory.projection import utc_instant
from app.shared.time import explicit_utc_instant


class ObservedRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    starts_at: datetime
    ends_at: datetime
    observed_starts_at: datetime
    observed_ends_at: datetime

    @model_validator(mode="after")
    def intervals(self):
        for name in ("starts_at", "ends_at", "observed_starts_at", "observed_ends_at"):
            setattr(self, name, utc_instant(getattr(self, name)))
        for start, end in ((self.starts_at, self.ends_at), (self.observed_starts_at, self.observed_ends_at)):
            if not timedelta(0) < end - start <= timedelta(days=366):
                raise ValueError("Positive intervals of at most 366 days required")
        return self


class ObservedItem(BaseModel):
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
    observed_quantity: str
    recorded_pace_projection: str
    complete_pace_projection: str | None
    recorded_projection_shortfall: str
    conditional_shortfall_after_all_orders: str


class ObservedRead(BaseModel):
    institute_id: str
    generated_at: datetime
    starts_at: datetime
    effective_starts_at: datetime
    ends_at: datetime
    observed_starts_at: datetime
    observed_ends_at: datetime
    source: Literal["signed_completed_service_usage"] = "signed_completed_service_usage"
    assumption: Literal["constant_elapsed_time_pace"] = "constant_elapsed_time_pace"
    coverage: Literal["complete_signed_sample", "partial_signed_sample", "no_completed_sample"]
    completed_executions: int
    captured_bases: int
    signed_confirmations: int
    pending_bases: int
    legacy_completed_executions: int
    undated_completed_executions: int
    limit: int
    offset: int
    items: list[ObservedItem]

    @field_serializer("generated_at", "starts_at", "effective_starts_at", "ends_at",
                      "observed_starts_at", "observed_ends_at")
    def instant(self, value):
        return explicit_utc_instant(value)
