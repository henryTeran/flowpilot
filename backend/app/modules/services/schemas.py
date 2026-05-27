from pydantic import BaseModel, ConfigDict, Field


class ServiceCategoryRead(BaseModel):
    id: str
    name: str
    code: str
    parent_id: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ServiceCreate(BaseModel):
    category_id: str
    name: str = Field(min_length=2, max_length=160)
    duration_min: int = Field(gt=0, le=480)
    duration_max: int | None = Field(default=None, gt=0, le=480)
    price_member: float | None = None
    price_passage: float | None = None
    requires_machine: bool = False
    requires_appointment: bool = False


class ServiceRead(BaseModel):
    id: str
    category_id: str
    name: str
    duration_min: int
    duration_max: int | None
    price_member: float | None
    price_passage: float | None
    requires_machine: bool
    requires_appointment: bool
    status: str

    model_config = ConfigDict(from_attributes=True)
