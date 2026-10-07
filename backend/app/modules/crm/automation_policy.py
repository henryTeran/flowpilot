"""Explicit internal-event rules; permissions never authorize outbound delivery."""
from typing import Annotated, Literal
from pydantic import Field, model_validator
from app.modules.crm.metrics import Fact, Identifier

Trigger = Literal["birthday", "post_service", "rebooking", "inactivity", "package_expiry", "subscription_renewal"]
Duration = Annotated[int, Field(strict=True, ge=0, le=253402300799999999)]


class AutomationRule(Fact):
    trigger: Trigger
    enabled: Annotated[bool, Field(strict=True)]
    # Delay after an observed anchor, or anticipation before an explicit expiry.
    offset_us: Duration

    @model_validator(mode="after")
    def explicit_timing(self):
        if self.trigger == "birthday" and self.offset_us != 0:
            raise ValueError("Birthday uses the declared civil day, not an elapsed-time offset")
        if self.trigger in {"rebooking", "inactivity"} and self.offset_us == 0:
            raise ValueError("Rebooking and inactivity require an explicit positive interval")
        return self


class AutomationPolicy(Fact):
    institute_id: Identifier
    rules: tuple[AutomationRule, ...]

    @model_validator(mode="after")
    def all_six_rules(self):
        expected = {"birthday", "post_service", "rebooking", "inactivity", "package_expiry", "subscription_renewal"}
        if len(self.rules) != 6 or {r.trigger for r in self.rules} != expected:
            raise ValueError("Explicitly declare each of the six lifecycle rules exactly once")
        return self
