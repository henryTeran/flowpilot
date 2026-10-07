"""Institute billing kernel. Inputs are captured facts, never predictive truth.

The source service must capture the entire paid-ticket cohort under its institute
lock. Invoice line totals describe mix, not a replacement for basket totals.
"""
from typing import Iterable, Literal
from pydantic import AwareDatetime, model_validator, field_validator
from app.modules.crm.metrics import Fact, Identifier, Minor, Count, Unsigned, ExactRatio


class Window(Fact):
    institute_id: Identifier
    start: AwareDatetime
    end: AwareDatetime
    captured_at: AwareDatetime

    @model_validator(mode="after")
    def observed(self):
        if not self.start < self.end <= self.captured_at:
            raise ValueError("An observed positive half-open window is required")
        return self


class TicketFact(Fact):
    institute_id: Identifier
    ticket_id: Identifier
    paid_at: AwareDatetime
    captured_at: AwareDatetime
    currency: Literal["CHF", "EUR"] | None
    amount_minor: Minor | None
    amount_quality: Literal["known", "missing", "invalid"]

    @model_validator(mode="after")
    def coherent(self):
        if self.paid_at > self.captured_at or (self.amount_quality == "known") != (self.amount_minor is not None):
            raise ValueError("Paid facts require coherent observed amounts")
        return self


class LineFact(Fact):
    institute_id: Identifier
    ticket_id: Identifier
    line_id: Identifier
    service_id: Identifier
    captured_at: AwareDatetime
    category: Literal["care", "retail"] | None
    quantity: Count
    amount_minor: Minor | None
    amount_quality: Literal["known", "missing", "invalid"]

    @field_validator("line_id", "service_id")
    @classmethod
    def exact_identifier(cls, value):
        if value != value.strip():
            raise ValueError("Exact source identifiers are required")
        return value

    @model_validator(mode="after")
    def coherent(self):
        if self.quantity == 0 or (self.amount_quality == "known") != (self.amount_minor is not None):
            raise ValueError("Active invoice facts require positive quantity and coherent amount")
        return self


class AmountGroup(Fact):
    currency: Literal["CHF", "EUR"] | None
    source_count: Count
    known_amount_count: Count
    missing_amount_count: Count
    invalid_amount_count: Count
    known_gross_minor: Unsigned
    complete_gross_minor: Unsigned | None
    average_minor: ExactRatio | None

    @model_validator(mode="after")
    def coherent(self):
        if not self.source_count or self.known_amount_count+self.missing_amount_count+self.invalid_amount_count != self.source_count:
            raise ValueError("Amount diagnostics must partition a nonempty source group")
        gross = int(self.known_gross_minor)
        if gross > self.known_amount_count*9999999999:
            raise ValueError("Known gross exceeds its recorded amount bounds")
        complete = self.currency is not None and self.known_amount_count == self.source_count
        if self.complete_gross_minor != (self.known_gross_minor if complete else None):
            raise ValueError("Complete gross cannot substitute for uncertain recorded amounts")
        expected = ExactRatio(numerator=self.known_gross_minor, denominator=str(self.source_count)) if complete else None
        if self.average_minor != expected:
            raise ValueError("Recorded average must use the entire complete source group")
        return self


class MixGroup(Fact):
    service_id: Identifier
    category: Literal["care", "retail"] | None
    currency: Literal["CHF", "EUR"] | None
    line_count: Count
    units: Unsigned
    amounts: AmountGroup


class Billing(Fact):
    window: Window
    basis: Literal["recorded_paid_tickets_and_active_invoice_lines"] = "recorded_paid_tickets_and_active_invoice_lines"
    ticket_count: Count
    ticket_amounts: tuple[AmountGroup, ...]
    active_line_count: Count
    service_mix: tuple[MixGroup, ...]
    tickets_without_active_lines: Count
    tickets_with_unknown_category: Count
    care_tickets: Count
    care_and_retail_tickets: Count
    recorded_retail_attach_ratio: ExactRatio | None
    institute_undated_paid_tickets: Count = 0
    complete_sales_history: Literal[False] = False
    settlement_confirmed: Literal[False] = False
    projected_revenue: None = None

    @field_validator("complete_sales_history", "settlement_confirmed", mode="before")
    @classmethod
    def no_claim(cls, value):
        if value is not False:
            raise ValueError("Unproven completeness or settlement cannot be asserted")
        return value

    @model_validator(mode="after")
    def coherent(self):
        currencies = [group.currency for group in self.ticket_amounts]
        if len(set(currencies)) != len(currencies) or sum(group.source_count for group in self.ticket_amounts) != self.ticket_count:
            raise ValueError("Unique currency groups must cover the ticket cohort")
        if self.care_and_retail_tickets > self.care_tickets or self.care_tickets > self.ticket_count \
                or self.tickets_without_active_lines > self.ticket_count or self.tickets_with_unknown_category > self.ticket_count:
            raise ValueError("Invoice category coverage must match the ticket cohort")
        expected = ExactRatio(numerator=str(self.care_and_retail_tickets), denominator=str(self.care_tickets)) \
            if self.care_tickets and not self.tickets_without_active_lines and not self.tickets_with_unknown_category else None
        if self.recorded_retail_attach_ratio != expected:
            raise ValueError("Attachment ratio must preserve category coverage")
        if sum(group.line_count for group in self.service_mix) != self.active_line_count:
            raise ValueError("Service mix must cover the active invoice lines")
        for group in self.service_mix:
            if group.currency != group.amounts.currency or group.line_count != group.amounts.source_count or int(group.units) < group.line_count:
                raise ValueError("Service mix source counts and extended amounts must agree")
        return self


def _add(group, source):
    group["source_count"] += 1
    group[source.amount_quality + "_amount_count"] += 1
    if source.amount_minor is not None:
        group["gross"] += int(source.amount_minor)


def _empty():
    return dict(source_count=0, known_amount_count=0, missing_amount_count=0, invalid_amount_count=0, gross=0)


def _amount(currency, group):
    complete = currency is not None and group["known_amount_count"] == group["source_count"]
    return AmountGroup(currency=currency, **{k: v for k, v in group.items() if k != "gross"},
        known_gross_minor=str(group["gross"]), complete_gross_minor=str(group["gross"]) if complete else None,
        average_minor=ExactRatio(numerator=str(group["gross"]), denominator=str(group["source_count"])) if complete and group["source_count"] else None)


def calculate(window: Window, tickets: Iterable[TicketFact], lines: Iterable[LineFact]) -> Billing:
    # Revalidate frozen models too: model_copy/model_construct are not authorities.
    window = Window.model_validate(window.model_dump())
    owners, groups, categories, seen_lines, mix = {}, {}, {}, set(), {}
    for source in tickets:
        source = TicketFact.model_validate(source.model_dump())
        if source.institute_id != window.institute_id or source.captured_at != window.captured_at \
                or not window.start <= source.paid_at < window.end or source.ticket_id in owners:
            raise ValueError("Unique paid tickets must share institute, capture and window")
        owners[source.ticket_id] = source.currency
        categories[source.ticket_id] = set()
        _add(groups.setdefault(source.currency, _empty()), source)
    for source in lines:
        source = LineFact.model_validate(source.model_dump())
        if source.institute_id != window.institute_id or source.captured_at != window.captured_at \
                or source.ticket_id not in owners or source.line_id in seen_lines:
            raise ValueError("Unique active invoice lines must belong to the captured ticket cohort")
        seen_lines.add(source.line_id)
        categories[source.ticket_id].add(source.category)
        key = (source.service_id, source.category, owners[source.ticket_id])
        group = mix.setdefault(key, dict(amounts=_empty(), units=0))
        _add(group["amounts"], source)
        group["units"] += source.quantity
    missing = sum(not kinds for kinds in categories.values())
    unknown = sum(None in kinds for kinds in categories.values())
    care = sum("care" in kinds for kinds in categories.values())
    attached = sum({"care", "retail"} <= kinds for kinds in categories.values())
    return Billing(window=window, ticket_count=len(owners),
        ticket_amounts=tuple(_amount(currency, groups[currency]) for currency in sorted(groups, key=lambda c: c or "")),
        active_line_count=len(seen_lines), service_mix=tuple(MixGroup(service_id=key[0], category=key[1], currency=key[2],
            line_count=group["amounts"]["source_count"], units=str(group["units"]), amounts=_amount(key[2], group["amounts"]))
            for key, group in sorted(mix.items(), key=lambda pair: tuple(value or "" for value in pair[0]))),
        tickets_without_active_lines=missing, tickets_with_unknown_category=unknown,
        care_tickets=care, care_and_retail_tickets=attached,
        recorded_retail_attach_ratio=ExactRatio(numerator=str(attached), denominator=str(care)) if care and not missing and not unknown else None)
