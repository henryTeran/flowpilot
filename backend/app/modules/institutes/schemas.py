from pydantic import BaseModel, ConfigDict


class InstituteRead(BaseModel):
    id: str
    name: str
    city: str
    address: str | None = None
    timezone: str
    status: str

    model_config = ConfigDict(from_attributes=True)
