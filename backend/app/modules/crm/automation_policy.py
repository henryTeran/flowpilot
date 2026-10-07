"""Explicit internal-event rules; permissions never authorize outbound delivery."""
import re
from typing import Annotated, Literal
from pydantic import Field, model_validator, field_validator, field_serializer
from app.modules.crm.metrics import Fact, Identifier

Trigger = Literal["birthday", "post_service", "rebooking", "inactivity", "package_expiry", "subscription_renewal"]
Duration = Annotated[int, Field(strict=True, ge=0, le=253402300799999999)]


def duration_schema(schema):
    canonical = {"type":"string","pattern":r"^(0|[1-9][0-9]*)$","maxLength":18}
    if schema.get("type")=="integer":
        for key in ("type","minimum","maximum"):schema.pop(key,None)
        schema["anyOf"]=[{"type":"integer","minimum":0,"maximum":253402300799999999},canonical]
    else:
        schema.update(canonical)


class AutomationRule(Fact):
    trigger: Trigger
    enabled: Annotated[bool, Field(strict=True)]
    # Delay after an observed anchor, or anticipation before an explicit expiry.
    offset_us: Duration = Field(json_schema_extra=duration_schema)

    @field_validator("offset_us", mode="before")
    @classmethod
    def exact_json_duration(cls, value):
        if isinstance(value, str):
            if len(value)>18 or not re.fullmatch(r"0|[1-9][0-9]*", value):
                raise ValueError("Canonical integer microseconds required")
            return int(value)
        return value

    @field_serializer("offset_us", when_used="json")
    def serialize_duration(self, value) -> str:
        return str(value)

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
