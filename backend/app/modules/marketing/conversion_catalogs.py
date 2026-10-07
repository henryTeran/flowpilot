"""Complete retained current-link cohort, never a page fragment or a sales prediction."""
from typing import Literal
from pydantic import AwareDatetime, model_validator
from sqlalchemy import select
from app.modules.crm.metrics import Fact, Count
from app.modules.marketing import conversion_originals, conversions, campaign_originals, catalogs
from app.modules.marketing.models import ConversionOriginal
from app.shared.exceptions import business_error, not_found
from app.shared.time import utcnow


class Request(Fact):
    start: AwareDatetime
    end: AwareDatetime

    @model_validator(mode="after")
    def chronology(self):
        if self.start >= self.end: raise ValueError("Explicit positive conversion reporting window required")
        return self


class Report(Fact):
    summary: conversions.Summary
    selected_current_links: Count
    full_retained_current_cohort: Literal[True] = True
    basis: Literal["current_declared_links_in_observed_billing_window"] = "current_declared_links_in_observed_billing_window"


def cohort(db, institute, campaign, payload):
    payload = Request.model_validate(payload.model_dump())
    catalogs.bounds(db, institute, 0, 20)
    at = utcnow()
    if campaign_originals.current(db, institute, campaign) is None: raise not_found("Campaign not found")
    try:
        window = conversions.SummaryWindow(institute_id=institute, campaign_id=campaign,
            start=payload.start, end=payload.end, captured_at=at)
    except ValueError:
        raise business_error("Conversion report requires an observed explicit window") from None
    # A historical candidate remains visible here after retraction/reassignment.
    # Missing heads must refuse, never turn orphaned history into zero conversions.
    tickets = db.scalars(select(ConversionOriginal.ticket_id).where(ConversionOriginal.institute_id == institute,
        ConversionOriginal.campaign_id == campaign).distinct().order_by(ConversionOriginal.ticket_id).execution_options(yield_per=100))
    def originals():
        for ticket in tickets:
            current = conversion_originals.current(db, institute, ticket)
            if current is None: raise business_error("Retained conversion history has no current pointer")
            if current.created_at > at: raise business_error("Conversion current event is future to report clock")
            if current.request.action == "linked" and current.attribution.intent.request.campaign_id == campaign and window.start <= current.attribution.ticket.closed_at < window.end:
                yield current
    return window, originals()


def report(db, institute, campaign, payload):
    window, originals = cohort(db, institute, campaign, payload)
    try:
        summary = conversions.summarize(window, (o.attribution for o in originals))
    except ValueError:
        raise business_error("Retained conversion cohort is incoherent") from None
    return Report(summary=summary, selected_current_links=summary.linked_tickets)


def current_links(db, institute, campaign, payload, offset=0, limit=20):
    catalogs.bounds(db, institute, offset, limit)
    _, originals = cohort(db, institute, campaign, payload)
    # Validate every participating candidate before exposing totals or a page;
    # memory retains only the requested bounded slice, not the whole cohort.
    count = 0; selected = []
    for original in originals:
        if offset <= count < offset + limit: selected.append(original)
        count += 1
    return catalogs.Page[conversion_originals.Original](institute_id=institute, total=count,
        offset=offset, limit=limit, items=tuple(selected))
