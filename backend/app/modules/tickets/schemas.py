from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TicketCreate(BaseModel):
    institute_id: str
    service_id: str
    customer_id: str | None = None
    subscription_id: str | None = None
    created_by_id: str | None = None


class TicketAssign(BaseModel):
    employee_id: str


class QueueTicketRead(BaseModel):
    id: str
    institute_id: str
    ticket_number: str
    customer_id: str | None
    subscription_id: str | None
    status: str
    arrival_time: datetime
    estimated_start_time: datetime | None
    assigned_employee_id: str | None
    created_by_id: str | None

    model_config = ConfigDict(from_attributes=True)


class TicketWithLinesRead(QueueTicketRead):
    lines: list[dict] = Field(default_factory=list)
