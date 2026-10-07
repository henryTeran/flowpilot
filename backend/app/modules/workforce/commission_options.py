"""Bounded explicit-rule closed-line choices; a preview never writes an accrual."""
from datetime import date
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import HTTPException
from pydantic import BaseModel, AwareDatetime
from sqlalchemy import select, func
from app.modules.institutes.models import Institute
from app.modules.institutes.calendar import day_bounds
from app.modules.tickets.models import TicketLine, QueueTicket
from app.modules.tickets.repository import lock_institute
from app.modules.workforce import commission_rules
from app.modules.workforce.commission_rule_schemas import CommissionRuleRead, calculation_terms
from app.modules.workforce.commission_sources import CommissionCalculation, capture_values, calculate
from app.modules.workforce.models import EmployeeCommission, CommissionCancellation
from app.modules.workforce.objectives import require_employee
from app.modules.workforce.schemas import MatrixPage
from app.shared.time import utcnow, explicit_utc_instant

Exclusion = Literal["rule_cancelled", "future_rule", "already_attributed", "future_cancellation", "future_closing", "currency_mismatch", "outside_period", "invalid_source"]


class SourceOption(BaseModel):
    line_id: str
    ticket_id: str
    service_id: str
    category: str
    quantity: int | None
    amount: Decimal | None
    currency: str | None
    arrival_at: AwareDatetime | None
    paid_at: AwareDatetime
    already_attributed: bool
    cancellation_clock_future: bool
    exclusion: Exclusion | None
    calculation: CommissionCalculation | None


class CommissionSourceOptions(BaseModel):
    institute_id: str
    employee_id: str
    rule: CommissionRuleRead
    day: date
    timezone: str
    start: AwareDatetime
    end: AwareDatetime
    generated_at: AwareDatetime
    basis: Literal["source_closed_day"] = "source_closed_day"
    complete_sources: Literal[False] = False
    page: MatrixPage
    rows: list[SourceOption]


def read(db, institute, rule_id, day, limit=20, offset=0):
    lock_institute(db, institute)
    rule = commission_rules.snapshot(db, commission_rules.require(db, institute, rule_id))
    require_employee(db, institute, rule.employee_id)
    start, end = day_bounds(db, institute, day); now = utcnow()
    try: zone = ZoneInfo(db.get(Institute, institute).timezone).key
    except (ZoneInfoNotFoundError, ValueError): zone = "UTC"
    own = (QueueTicket.institute_id == institute, QueueTicket.status == "paid", QueueTicket.paid_at >= start,
        QueueTicket.paid_at < end, TicketLine.invoice_removed_at.is_(None),
        TicketLine.performed_by_employee_id == rule.employee_id, TicketLine.revenue_category == rule.category)
    if rule.service_id is not None: own += (TicketLine.service_id == rule.service_id,)
    def joined(query):
        return query.select_from(TicketLine).join(QueueTicket, QueueTicket.id == TicketLine.ticket_id).where(*own)
    total = db.scalar(joined(select(func.count())))
    active = select(EmployeeCommission.id).outerjoin(CommissionCancellation,
        (CommissionCancellation.institute_id == EmployeeCommission.institute_id)
        & (CommissionCancellation.commission_id == EmployeeCommission.id)).where(
        EmployeeCommission.institute_id == institute, EmployeeCommission.line_id == TicketLine.id,
        CommissionCancellation.id.is_(None)).exists()
    future_cancel = select(CommissionCancellation.id).join(EmployeeCommission,
        (CommissionCancellation.institute_id == EmployeeCommission.institute_id)
        & (CommissionCancellation.commission_id == EmployeeCommission.id)).where(
        EmployeeCommission.institute_id == institute, EmployeeCommission.line_id == TicketLine.id,
        CommissionCancellation.created_at > now).exists()
    rows = db.execute(joined(select(TicketLine, QueueTicket, active, future_cancel))
        .order_by(QueueTicket.paid_at.desc(), QueueTicket.id, TicketLine.id).offset(offset).limit(limit))
    values = []
    for line, ticket, attributed, cancellation_future in rows:
        paid = explicit_utc_instant(ticket.paid_at)
        exclusion = "rule_cancelled" if rule.cancellation else "future_rule" if rule.created_at > now else \
            "already_attributed" if attributed else "future_cancellation" if cancellation_future else "future_closing" if paid > now else \
            "currency_mismatch" if ticket.currency != rule.currency else \
            "outside_period" if not rule.period_start <= paid < rule.period_end else None
        preview = None
        if exclusion is None:
            try: preview = calculate(calculation_terms(rule), capture_values(line, ticket, institute, True, now))
            except HTTPException: exclusion = "invalid_source"
        values.append(SourceOption(line_id=line.id, ticket_id=ticket.id, service_id=line.service_id,
            category=line.revenue_category, quantity=line.quantity if type(line.quantity) is int else None,
            amount=line.total if isinstance(line.total, Decimal) and line.total.is_finite() else None, currency=ticket.currency,
            arrival_at=explicit_utc_instant(ticket.arrival_time), paid_at=paid, already_attributed=bool(attributed),
            cancellation_clock_future=bool(cancellation_future),
            exclusion=exclusion, calculation=preview))
    return CommissionSourceOptions(institute_id=institute, employee_id=rule.employee_id, rule=rule,
        day=day, timezone=zone, start=start, end=end, generated_at=now,
        page=MatrixPage(offset=offset, limit=limit, total=total), rows=values)
