"""Explicit commission terms, retained closed-line captures and exact arithmetic.

Capture caller must hold the institute transaction lock. This contract does not
configure a default rule, write an accrual or establish payment/payroll liability.
"""
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Annotated, Literal
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictInt, StringConstraints, field_validator, model_validator
from sqlalchemy import select
from app.modules.employees.models import Employee
from app.modules.tickets.models import QueueTicket, TicketLine
from app.shared.exceptions import business_error, not_found
from app.shared.time import explicit_utc_instant

Identifier = Annotated[str, StringConstraints(min_length=1, max_length=80)]
Minor = Annotated[str, StringConstraints(pattern=r"^(0|[1-9][0-9]*)$", max_length=30)]
Currency = Literal["CHF", "EUR"]


def explicit_instant(value):
    if (not isinstance(value, (str, datetime)) or isinstance(value, datetime) and value.utcoffset() is None
        or isinstance(value, str) and "T" not in value):
        raise ValueError("An explicit aware ISO instant is required")
    return value


class CommissionTerms(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    employee_id: Identifier
    basis: Literal["closed_attributed_line_gross"]
    currency: Currency
    category: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
    service_id: Identifier | None  # Explicit null means all services in the category.
    rate_basis_points: StrictInt = Field(ge=0, le=10000)
    rounding: Literal["half_up", "half_even", "down"]
    period_start: AwareDatetime
    period_end: AwareDatetime

    @field_validator("period_start", "period_end", mode="before")
    @classmethod
    def explicit_period(cls, value):
        return explicit_instant(value)

    @model_validator(mode="after")
    def positive_period(self):
        if self.period_end <= self.period_start:
            raise ValueError("A positive half-open period is required")
        return self


class ClosedLineCapture(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    institute_id: Identifier
    ticket_id: Identifier
    line_id: Identifier
    employee_id: Identifier
    service_id: Identifier
    category: Annotated[str, StringConstraints(min_length=1, max_length=40)]
    currency: Currency
    quantity: StrictInt = Field(ge=1)
    gross_minor: Minor  # Full line total, already including its quantity.
    arrival_at: AwareDatetime
    paid_at: AwareDatetime
    captured_at: AwareDatetime

    @field_validator("arrival_at", "paid_at", "captured_at", mode="before")
    @classmethod
    def explicit_clock(cls, value):
        return explicit_instant(value)

    @model_validator(mode="after")
    def chronology(self):
        if not self.arrival_at <= self.paid_at <= self.captured_at:
            raise ValueError("Closed source chronology is incoherent")
        return self


class CommissionCalculation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    terms: CommissionTerms
    source: ClosedLineCapture
    unrounded_numerator: Minor  # gross_minor * rate; divisor is exactly 10000.
    rounding_remainder: StrictInt = Field(ge=0, lt=10000)
    amount_minor: Minor


def exact_minor(value):
    """Read Numeric(10,2) without ambient Decimal rounding or float coercion."""
    if not isinstance(value, (str, Decimal)):
        raise business_error("An exact retained line amount is required")
    try:
        amount = Decimal(value)
    except InvalidOperation as error:
        raise business_error("The retained line amount is invalid") from error
    if not amount.is_finite() or amount < 0 or amount > Decimal("99999999.99"):
        raise business_error("The retained line amount is outside its source contract")
    if amount.is_zero():
        return 0
    _, digits, exponent = amount.as_tuple()
    if exponent < -2:
        extra = -2-exponent
        if extra >= len(digits) or any(digits[-extra:]):
            raise business_error("Fractional cents cannot define a commission source")
        digits = digits[:-extra]
        exponent = -2
    coefficient = int("".join(map(str, digits)))
    return coefficient * 10**(exponent+2)


def capture(db, institute, line_id, now):
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise business_error("An explicit capture clock is required")
    row = db.execute(select(TicketLine, QueueTicket).join(QueueTicket, QueueTicket.id == TicketLine.ticket_id)
        .where(QueueTicket.institute_id == institute, TicketLine.id == line_id)).first()
    if row is None:
        raise not_found("Commission source line not found")
    line, ticket = row
    if ticket.status != "paid" or line.invoice_removed_at is not None:
        raise business_error("Only retained internally closed lines can define this basis")
    if ticket.paid_at is None or ticket.currency not in ("CHF", "EUR"):
        raise business_error("The source closing instant and currency must be known")
    if not line.performed_by_employee_id or not db.scalar(select(Employee.id).where(
        Employee.institute_id == institute, Employee.id == line.performed_by_employee_id)):
        raise business_error("An owned actual performer is required; the cashier is not inferred")
    try:
        return ClosedLineCapture(institute_id=institute, ticket_id=ticket.id, line_id=line.id,
            employee_id=line.performed_by_employee_id, service_id=line.service_id, category=line.revenue_category,
            currency=ticket.currency, quantity=line.quantity, gross_minor=str(exact_minor(line.total)),
            arrival_at=explicit_utc_instant(ticket.arrival_time), paid_at=explicit_utc_instant(ticket.paid_at), captured_at=now)
    except ValueError as error:
        raise business_error("The retained source terms or chronology are incoherent") from error


def calculate(terms: CommissionTerms, source: ClosedLineCapture):
    if (terms.employee_id != source.employee_id or terms.currency != source.currency
        or terms.category != source.category or terms.service_id is not None and terms.service_id != source.service_id
        or not terms.period_start <= source.paid_at < terms.period_end):
        raise business_error("The explicit rule terms do not cover this captured source")
    numerator = int(source.gross_minor) * terms.rate_basis_points
    quotient, remainder = divmod(numerator, 10000)
    increment = terms.rounding == "half_up" and remainder >= 5000 or terms.rounding == "half_even" and (
        remainder > 5000 or remainder == 5000 and quotient % 2 == 1)
    return CommissionCalculation(terms=terms, source=source, unrounded_numerator=str(numerator),
        rounding_remainder=remainder, amount_minor=str(quotient+int(increment)))
