from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TicketCreate(BaseModel):
    institute_id: str
    # Compatibilité avec l'ancien workflow : un seul service_id.
    service_id: str | None = None
    # Nouveau workflow BodyMinute-like : plusieurs prestations dans un même ticket.
    service_ids: list[str] = Field(default_factory=list)
    customer_id: str | None = None
    subscription_id: str | None = None
    created_by_id: str | None = None

    @model_validator(mode="after")
    def require_at_least_one_service(self):
        if not self.service_id and not self.service_ids:
            raise ValueError("Au moins une prestation est obligatoire")
        return self


class TicketAssign(BaseModel):
    employee_id: str


class TicketLineRead(BaseModel):
    id: str
    ticket_id: str
    service_id: str
    quantity: int
    unit_price: float | None
    total: float | None
    duration_minutes: int
    revenue_category: str
    # Champ calculé côté route : pending / in_progress / completed.
    status: str = "pending"

    model_config = ConfigDict(from_attributes=True)


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
    lines: list[TicketLineRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class TicketWithLinesRead(QueueTicketRead):
    lines: list[TicketLineRead] = Field(default_factory=list)
