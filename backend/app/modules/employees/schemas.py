from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from typing import Annotated, Literal

EmployeeStatus = Literal["available", "busy", "pause", "absent", "offline"]


class EmployeeCreate(BaseModel):
    institute_id: str
    first_name: str = Field(min_length=2, max_length=120)
    code: str | None = None
    skills: list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]] = Field(default_factory=list, max_length=100)
    status: EmployeeStatus = "available"


class EmployeeRead(BaseModel):
    id: str
    institute_id: str
    first_name: str
    code: str | None
    skills: list[str]
    status: str

    model_config = ConfigDict(from_attributes=True)


class EmployeeStatusUpdate(BaseModel):
    status: str
