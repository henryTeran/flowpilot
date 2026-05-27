from pydantic import BaseModel, ConfigDict, Field


class EmployeeCreate(BaseModel):
    institute_id: str
    first_name: str = Field(min_length=2, max_length=120)
    code: str | None = None
    skills: list[str] = Field(default_factory=list)
    status: str = "available"


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
