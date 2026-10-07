"""Recorded employee attribution on internally closed invoice lines."""
from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from pydantic import AwareDatetime, BaseModel, field_validator
from sqlalchemy import func, select
from app.modules.employees.models import Employee
from app.modules.institutes.calendar import day_bounds
from app.modules.tickets.models import QueueTicket, TicketLine
from app.modules.tickets.repository import lock_institute
from app.modules.workforce.schemas import MatrixPage
from app.shared.exceptions import not_found
from app.shared.time import explicit_utc_instant, utcnow


class RevenueLine(BaseModel):
    id: str
    ticket_id: str
    ticket_number: str
    service_id: str
    employee_id: str
    paid_at: AwareDatetime
    currency: Literal["CHF", "EUR"] | None
    category: str
    quantity: int
    amount: Decimal | None

    @field_validator("paid_at", mode="before")
    @classmethod
    def aware(cls, value):
        return explicit_utc_instant(value) if isinstance(value, datetime) else value


class RevenueCurrency(BaseModel):
    currency: Literal["CHF", "EUR"] | None
    line_count: int
    ticket_count: int
    amount_known_total: Decimal | None
    amount_missing_lines: int
    total: Decimal | None


class EmployeeRevenue(BaseModel):
    institute_id: str
    employee_id: str
    day: date
    start: AwareDatetime
    end: AwareDatetime
    generated_at: AwareDatetime
    page: MatrixPage
    rows: list[RevenueLine]
    currencies: list[RevenueCurrency]
    institute_unattributed_lines: int


def closed_line_conditions(institute, start, end):
    return (QueueTicket.institute_id == institute, QueueTicket.status == "paid",
            QueueTicket.paid_at >= start, QueueTicket.paid_at < end, TicketLine.invoice_removed_at.is_(None))


def read(db, institute, employee, day, limit=50, offset=0):
    lock_institute(db, institute)
    if not db.scalar(select(Employee.id).where(Employee.institute_id == institute, Employee.id == employee)):
        raise not_found("Collaboratrice introuvable")
    start, end = day_bounds(db, institute, day)
    closed = closed_line_conditions(institute, start, end)
    own = (*closed, TicketLine.performed_by_employee_id == employee)
    source = lambda query: query.select_from(TicketLine).join(QueueTicket, QueueTicket.id == TicketLine.ticket_id)
    total = db.scalar(source(select(func.count())).where(*own))
    unknown = db.scalar(source(select(func.count())).where(*closed, TicketLine.performed_by_employee_id.is_(None)))
    groups = []
    for currency, count, tickets, known, amounts in db.execute(source(select(QueueTicket.currency, func.count(),
        func.count(func.distinct(QueueTicket.id)), func.sum(TicketLine.total), func.count(TicketLine.total)))
        .where(*own).group_by(QueueTicket.currency).order_by(QueueTicket.currency)):
        missing = count-amounts
        groups.append(dict(currency=currency, line_count=count, ticket_count=tickets,
                           amount_known_total=(known or Decimal("0.00")) if currency is not None else None, amount_missing_lines=missing,
                           total=known if not missing and currency is not None else None))
    rows = [dict(id=line.id, ticket_id=ticket.id, ticket_number=ticket.ticket_number, service_id=line.service_id,
                 employee_id=line.performed_by_employee_id, paid_at=ticket.paid_at, currency=ticket.currency,
                 category=line.revenue_category, quantity=line.quantity, amount=line.total)
            for line, ticket in db.execute(source(select(TicketLine, QueueTicket)).where(*own)
                .order_by(QueueTicket.paid_at, QueueTicket.id, TicketLine.id).limit(limit).offset(offset))]
    return dict(institute_id=institute, employee_id=employee, day=day, start=start, end=end, generated_at=utcnow(),
                page=dict(offset=offset, limit=limit, total=total), rows=rows, currencies=groups,
                institute_unattributed_lines=unknown)
