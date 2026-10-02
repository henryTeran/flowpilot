from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TicketCreate(BaseModel):
    institute_id: str
    # Compatibilité avec l'ancien workflow : un seul service_id.
    service_id: str | None = None
    # Nouveau workflow multi-prestations : plusieurs prestations dans un même ticket.
    service_ids: list[str] = Field(default_factory=list)
    customer_id: str | None = None
    subscription_id: str | None = None
    created_by_id: str | None = None
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=120)

    @model_validator(mode="after")
    def require_at_least_one_service(self):
        if not self.service_id and not self.service_ids:
            raise ValueError("Au moins une prestation est obligatoire")
        return self


class TicketAssign(BaseModel):
    employee_id: str


class TicketCheckoutStart(BaseModel):
    employee_id: str


class TicketPaymentComplete(BaseModel):
    employee_id: str
    payment_method: str = "cb"


class TicketLineAdd(BaseModel):
    service_id: str


class TicketLineRead(BaseModel):
    id: str
    ticket_id: str
    service_id: str
    quantity: int
    unit_price: float | None
    total: float | None
    duration_minutes: int
    revenue_category: str
    performed_by_employee_id: str | None = None
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
    assigned_at: datetime | None = None
    cancelled_at: datetime | None = None
    queue_position: int | None = None
    assignment_state: str = "unassigned"
    standard_duration_minutes: int = 0
    created_by_id: str | None
    checkout_employee_id: str | None = None
    checkout_started_at: datetime | None = None
    paid_employee_id: str | None = None
    paid_at: datetime | None = None
    payment_method: str | None = None
    total_amount: float | None = None
    lines: list[TicketLineRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class QueueEventRead(BaseModel):
    id: int
    institute_id: str
    ticket_id: str
    event_type: str
    previous_status: str | None
    status: str
    employee_id: str | None
    occurred_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TicketWithLinesRead(QueueTicketRead):
    lines: list[TicketLineRead] = Field(default_factory=list)


class EmployeeChiffresRead(BaseModel):
    """Ligne du module Chiffres, proche du logiciel caisse actuel."""

    employee_id: str
    employee_name: str
    soins: float = 0.0
    ventes: float = 0.0
    contrats: float = 0.0
    pourboires: float = 0.0
    moyenne: float = 0.0
    total: float = 0.0
    tickets: int = 0
    prestations: int = 0


class ChiffresSummaryRead(BaseModel):
    institute_id: str
    generated_at: datetime
    period_start: datetime
    period_end: datetime
    rows: list[EmployeeChiffresRead]
    totals: EmployeeChiffresRead
