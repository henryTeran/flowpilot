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
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=120, pattern=r".*\S.*")


class AppointmentUpdateStatus(BaseModel):
    status: str


class AppointmentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start_time: datetime | None = None
    employee_id: str | None = Field(default=None, min_length=1)
    service_id: str | None = Field(default=None, min_length=1)
    customer_name: str | None = Field(default=None, min_length=2, max_length=160)
    phone: str | None = Field(default=None, max_length=40)
    notes: str | None = Field(default=None, max_length=500)


class AppointmentRead(BaseModel):
    id: str
    institute_id: str
    service_id: str
    employee_id: str
    customer_name: str
    phone: str | None
    start_time: datetime
    end_time: datetime
    booked_start_time: datetime | None = None
    booked_end_time: datetime | None = None
    actual_start_time: datetime | None = None
    actual_end_time: datetime | None = None
    status: str
    notes: str | None

    model_config = ConfigDict(from_attributes=True)
