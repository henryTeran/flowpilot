from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AppointmentCreate(BaseModel):
    institute_id: str
    service_id: str
    employee_id: str
    customer_name: str = Field(min_length=2, max_length=160)
    phone: str | None = Field(default=None, max_length=40)
    start_time: datetime
    notes: str | None = Field(default=None, max_length=500)


class AppointmentUpdateStatus(BaseModel):
    status: str


class AppointmentRead(BaseModel):
    id: str
    institute_id: str
    service_id: str
    employee_id: str
    customer_name: str
    phone: str | None
    start_time: datetime
    end_time: datetime
    status: str
    notes: str | None

    model_config = ConfigDict(from_attributes=True)
