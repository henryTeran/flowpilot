from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator, field_serializer


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


class TicketCustomerAttach(BaseModel):
    model_config = ConfigDict(extra="forbid")
    customer_id: str | None = Field(min_length=1, max_length=80)


class TicketCurrencyConfirm(BaseModel):
    model_config = ConfigDict(extra="forbid")
    currency: Literal["CHF", "EUR"]
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=240)]


class TicketPaymentComplete(BaseModel):
    model_config = ConfigDict(extra="forbid")
    employee_id: str
    payment_method: str = "cb"
    remainder_method: Literal["cb", "especes", "cheque"] | None = None


class TicketLineAdd(BaseModel):
    service_id: str


class TicketLineRead(BaseModel):
    commercial_history: bool = False
    id: str
    ticket_id: str
    service_id: str
    quantity: int
    unit_price: float | None
    total: float | None
    duration_minutes: int
    revenue_category: str
    performed_by_employee_id: str | None = None
    invoice_removed_at: datetime | None = None
    invoice_removed_by_actor: str | None = None
    invoice_removal_reason: Literal["not_performed"] | None = None

    @field_serializer("invoice_removed_at")
    def removal_timestamp(self, value):
        from app.shared.time import explicit_utc_instant
        return explicit_utc_instant(value)

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
    currency: str | None = None
    lines: list[TicketLineRead] = Field(default_factory=list)
    removed_lines: list[TicketLineRead] = Field(default_factory=list)

    @field_serializer("arrival_time", "estimated_start_time", "assigned_at", "cancelled_at", "checkout_started_at", "paid_at")
    def timestamps(self, value):
        from app.shared.time import explicit_utc_instant
        return explicit_utc_instant(value)

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

    @field_serializer("occurred_at")
    def timestamp(self, value):
        from app.shared.time import explicit_utc_instant
        return explicit_utc_instant(value)

    model_config = ConfigDict(from_attributes=True)


class TicketWithLinesRead(QueueTicketRead):
    lines: list[TicketLineRead] = Field(default_factory=list)


class EmployeeChiffresRead(BaseModel):
    """Ligne du module Chiffres, proche du logiciel caisse actuel."""

    employee_id: str
    employee_name: str
    soins: Decimal | None = Decimal("0.00")
    ventes: Decimal | None = Decimal("0.00")
    contrats: Decimal | None = Decimal("0.00")
    pourboires: Decimal | None = Decimal("0.00")
    moyenne: Decimal | None = Decimal("0.00")
    total: Decimal | None = Decimal("0.00")
    tickets: int = 0
    prestations: int = 0


    @field_serializer("soins", "ventes", "contrats", "pourboires", "moyenne", "total")
    def monetary_text(self, value):
        return format(value, ".2f") if value is not None else None


class CurrencyChiffresRead(BaseModel):
    currency: Literal["CHF", "EUR"]
    rows: list[EmployeeChiffresRead]
    totals: EmployeeChiffresRead


class ChiffresSummaryRead(BaseModel):
    institute_id: str
    currency: Literal["CHF", "EUR"] | None = None
    currency_groups: list[CurrencyChiffresRead] = Field(default_factory=list)
    unknown_currency_tickets: int = 0
    generated_at: datetime
    period_start: datetime
    period_end: datetime
    rows: list[EmployeeChiffresRead]
    totals: EmployeeChiffresRead
