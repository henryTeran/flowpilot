"""Recorded upcoming demand; provisional norms, not a demand prediction."""
from datetime import datetime, timedelta
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator, field_serializer
from app.modules.inventory.outlook_schemas import OutlookItem
from app.modules.inventory.projection import utc_instant
from app.shared.time import explicit_utc_instant


class PlannedRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    starts_at: datetime
    ends_at: datetime
    include_waiting_queue: bool = Field(strict=True)

    @model_validator(mode="after")
    def interval(self):
        self.starts_at = utc_instant(self.starts_at)
        self.ends_at = utc_instant(self.ends_at)
        if not timedelta(0) < self.ends_at - self.starts_at <= timedelta(days=366):
            raise ValueError("Positive horizon of at most 366 days required")
        return self


class PlannedRead(BaseModel):
    institute_id: str
    generated_at: datetime
    starts_at: datetime
    effective_starts_at: datetime
    ends_at: datetime
    include_waiting_queue: bool
    source: Literal["recorded_upcoming_demand"] = "recorded_upcoming_demand"
    norm_basis: Literal["provisional_current_at_read"] = "provisional_current_at_read"
    queue_timing: Literal["unscheduled_at_read"] = "unscheduled_at_read"
    coverage: Literal["complete_recorded_norms", "partial_recorded_norms"]
    appointment_count: int
    waiting_line_count: int
    service_quantity: int
    missing_norm_quantity: int
    disabled_norm_quantity: int
    limit: int
    offset: int
    items: list[OutlookItem]

    @field_serializer("generated_at", "starts_at", "effective_starts_at", "ends_at")
    def instant(self, value):
        return explicit_utc_instant(value)
