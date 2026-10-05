from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Code = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Kind = Literal["room", "equipment", "bed", "chair", "device"]
ResourceStatus = Literal["active", "inactive", "maintenance"]


class SkillUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    skills: list[Code] = Field(max_length=100)

    @model_validator(mode="after")
    def unique_codes(self):
        if len(set(self.skills)) != len(self.skills):
            raise ValueError("Chaque competence doit etre unique")
        return self


class ResourceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Name
    kind: Kind
    capabilities: list[Code] = Field(default_factory=list, max_length=100)
    status: ResourceStatus = "active"


class ResourceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Name | None = None
    capabilities: list[Code] | None = Field(default=None, max_length=100)
    status: ResourceStatus | None = None


class ResourceRead(ResourceCreate):
    id: str
    institute_id: str
    model_config = ConfigDict(from_attributes=True)


class ResourceNeed(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Kind
    capability: Code | None = None
    quantity: int = Field(default=1, ge=1, le=10)


class RequirementUpdate(SkillUpdate):
    resources: list[ResourceNeed] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def unique_resources(self):
        if len({(need.kind, need.capability) for need in self.resources}) != len(self.resources):
            raise ValueError("Chaque exigence de ressource doit etre unique")
        return self
