"""Exact recorded-commission day, without entitlement or settlement inference."""
from datetime import date
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pydantic import BaseModel, AwareDatetime
from sqlalchemy import select
from app.modules.workforce.commissions import CommissionRead, dto
from app.modules.workforce.models import EmployeeCommission as Original, CommissionCancellation as Cancellation
from app.modules.institutes.models import Institute
from app.modules.institutes.calendar import day_bounds
from app.modules.workforce.objectives import require_employee
from app.modules.workforce.schemas import MatrixPage
from app.modules.tickets.repository import lock_institute
from app.shared.time import utcnow

State = Literal["recorded", "cancelled", "future_recording", "future_cancellation"]
STATES = ("recorded", "cancelled", "future_recording", "future_cancellation")


class CommissionDayRow(BaseModel):
    original: CommissionRead
    state: State


class CurrencyTotals(BaseModel):
    currency: Literal["CHF", "EUR"]
    counts: dict[str, int]
    amounts_minor: dict[str, str]


class CommissionDay(BaseModel):
    institute_id: str
    employee_id: str
    day: date
    timezone: str
    start: AwareDatetime
    end: AwareDatetime
    generated_at: AwareDatetime
    basis: Literal["commission_recorded_at"] = "commission_recorded_at"
    page: MatrixPage
    rows: list[CommissionDayRow]
    counts: dict[str, int]
    currencies: list[CurrencyTotals]
    complete_entitlement: Literal[False] = False
    payable_total: None = None


def classify(original, now):
    if original.created_at > now: return "future_recording"
    if original.cancellation:
        return "future_cancellation" if original.cancellation.created_at > now else "cancelled"
    return "recorded"


def read(db, institute, employee, day, limit=20, offset=0):
    lock_institute(db, institute); require_employee(db, institute, employee)
    start, end = day_bounds(db, institute, day); now = utcnow()
    try: zone = ZoneInfo(db.get(Institute, institute).timezone).key
    except (ZoneInfoNotFoundError, ValueError): zone = "UTC"
    own = (Original.institute_id == institute, Original.employee_id == employee,
        Original.created_at >= start, Original.created_at < end)
    query = select(Original, Cancellation).outerjoin(Cancellation,
        (Cancellation.institute_id == Original.institute_id) & (Cancellation.commission_id == Original.id)).where(*own)
    counts = dict.fromkeys(STATES, 0); currencies = {}
    # Validate each retained authority before admitting it to global amounts.
    # Streaming keeps memory bounded; exact Python integers avoid SQLite SUM drift.
    for row, cancelled in db.execute(query.execution_options(yield_per=100)):
        original = dto(row, cancelled); state = classify(original, now)
        currency = original.calculation.source.currency
        if currency not in currencies:
            currencies[currency] = (dict.fromkeys(STATES, 0), dict.fromkeys(STATES, 0))
        group_counts, amounts = currencies[currency]
        counts[state] += 1; group_counts[state] += 1
        amounts[state] += int(original.calculation.amount_minor)
    rows = db.execute(query.order_by(Original.created_at.desc(), Original.id).offset(offset).limit(limit))
    page_rows = []
    for row, cancelled in rows:
        original = dto(row, cancelled)
        page_rows.append(CommissionDayRow(original=original, state=classify(original, now)))
    return CommissionDay(institute_id=institute, employee_id=employee, day=day, timezone=zone, start=start, end=end,
        generated_at=now, page=MatrixPage(offset=offset, limit=limit, total=sum(counts.values())), counts=counts,
        currencies=[CurrencyTotals(currency=currency, counts=values[0], amounts_minor={state: str(value) for state, value in values[1].items()})
            for currency, values in sorted(currencies.items())],
        rows=page_rows)
