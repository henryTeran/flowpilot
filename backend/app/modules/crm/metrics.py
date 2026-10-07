"""Exact recorded billing metrics; neither visits nor predictive lifetime value."""
from datetime import datetime
from typing import Annotated, Iterable, Literal
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, model_validator, field_validator

Identifier = Annotated[str, StringConstraints(min_length=1, max_length=80)]
Minor = Annotated[str, StringConstraints(pattern=r"^(0|[1-9][0-9]*)$", max_length=10)]
Count = Annotated[int, Field(strict=True, ge=0)]
Unsigned = Annotated[str, StringConstraints(pattern=r"^(0|[1-9][0-9]*)$")]


class Fact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("*", mode="before")
    @classmethod
    def explicit_values(cls, value, info):
        if value is not None and (info.field_name.endswith("_at") or info.field_name in {"start", "end"}):
            if not isinstance(value, (str, datetime)) or isinstance(value, datetime) and value.utcoffset() is None or isinstance(value, str) and "T" not in value:
                raise ValueError("An explicit aware ISO instant is required")
        if info.field_name in {"institute_id", "customer_id", "ticket_id"} and isinstance(value, str) and value.strip() != value:
            raise ValueError("An exact scoped identifier is required")
        return value


class BillingWindow(Fact):
    institute_id: Identifier
    customer_id: Identifier
    start: AwareDatetime
    end: AwareDatetime
    captured_at: AwareDatetime

    @model_validator(mode="after")
    def chronology(self):
        if not self.start < self.end <= self.captured_at:
            raise ValueError("A positive observed half-open window is required")
        return self


class ClosedTicketFact(Fact):
    institute_id: Identifier
    customer_id: Identifier
    ticket_id: Identifier
    closed_at: AwareDatetime
    captured_at: AwareDatetime
    currency: Literal["CHF", "EUR"] | None
    amount_minor: Minor | None
    amount_quality: Literal["known", "missing", "invalid"]

    @model_validator(mode="after")
    def coherent(self):
        if self.closed_at > self.captured_at:
            raise ValueError("A future closing cannot be a retained billing fact")
        if (self.amount_quality == "known") != (self.amount_minor is not None):
            raise ValueError("Known gross and source diagnostics must agree")
        return self


class ExactRatio(Fact):
    numerator: str = Field(pattern=r"^(0|[1-9][0-9]*)$")
    denominator: int = Field(strict=True, gt=0)


class CurrencyBilling(Fact):
    currency: Literal["CHF", "EUR"]
    closed_tickets: Count
    known_amount_tickets: Count
    missing_amount_tickets: Count
    invalid_amount_tickets: Count
    known_gross_minor: Unsigned
    recorded_average_basket_minor: ExactRatio | None


class RecordedBilling(Fact):
    window: BillingWindow
    basis: Literal["retained_closed_tickets"] = "retained_closed_tickets"
    closed_tickets: Count
    frequency_per_microsecond: ExactRatio
    last_recorded_closed_at: AwareDatetime | None
    recorded_recency_us: Unsigned | None
    unknown_currency_tickets: Count
    currencies: tuple[CurrencyBilling, ...]
    complete_customer_history: Literal[False] = False
    complete_currency_classification: bool
    predicted_clv: None = None


def microseconds(delta):
    return delta.days*86400000000 + delta.seconds*1000000 + delta.microseconds


def calculate_billing(window: BillingWindow, facts: Iterable[ClosedTicketFact]) -> RecordedBilling:
    """Caller captures a scoped cohort; page fragments cannot stand for this cohort."""
    ids = set(); last = None; unknown_currency = 0
    groups = {}
    for fact in facts:
        if fact.institute_id != window.institute_id or fact.customer_id != window.customer_id or fact.captured_at != window.captured_at:
            raise ValueError("Billing source scope or capture differs from the window")
        if not window.start <= fact.closed_at < window.end or fact.ticket_id in ids:
            raise ValueError("Billing sources must be unique and inside the half-open window")
        ids.add(fact.ticket_id)
        last = max(last, fact.closed_at) if last else fact.closed_at
        if fact.currency is None:
            unknown_currency += 1
            continue
        group = groups.setdefault(fact.currency, {"count": 0, "known": 0, "missing": 0, "invalid": 0, "minor": 0})
        group["count"] += 1; group[fact.amount_quality] += 1
        if fact.amount_minor is not None: group["minor"] += int(fact.amount_minor)
    currencies = tuple(CurrencyBilling(currency=currency, closed_tickets=g["count"], known_amount_tickets=g["known"],
        missing_amount_tickets=g["missing"], invalid_amount_tickets=g["invalid"], known_gross_minor=str(g["minor"]),
        recorded_average_basket_minor=ExactRatio(numerator=str(g["minor"]), denominator=g["count"]) if g["known"] == g["count"] else None)
        for currency, g in sorted(groups.items()))
    return RecordedBilling(window=window, closed_tickets=len(ids), frequency_per_microsecond=ExactRatio(numerator=str(len(ids)), denominator=microseconds(window.end-window.start)),
        last_recorded_closed_at=last, recorded_recency_us=str(microseconds(window.captured_at-last)) if last else None,
        unknown_currency_tickets=unknown_currency, currencies=currencies, complete_currency_classification=unknown_currency == 0)
