"""Explicit historical-rate closure scenario; not paid or agreed-price truth."""
from typing import Annotated, Literal
from pydantic import StringConstraints, field_validator
from sqlalchemy import select, func
from app.modules.crm.metrics import Fact, Identifier, Minor
from app.modules.revenue import booking_references as refs, closures
from app.modules.revenue.billing import Window
from app.modules.appointments.models import BookingEvent, Appointment
from app.modules.appointments.events import snapshot
from app.modules.tickets.repository import lock_institute
from app.shared.exceptions import business_error, not_found
from app.shared.time import utcnow, explicit_utc_instant


class Request(Fact):
    reference_event_id: Identifier
    expected_fingerprint: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    closure_event_id: Identifier
    rate: Literal["member", "passage"]
    reason: Annotated[str, StringConstraints(min_length=3, max_length=240)]


class Value(Fact):
    currency: Literal["CHF", "EUR"]
    amount_minor: Minor
    basis: Literal["explicit_historical_catalog_rate_scenario"] = "explicit_historical_catalog_rate_scenario"


class Preview(Fact):
    type: Literal["review_booking_closure_reference_value"] = "review_booking_closure_reference_value"
    actor_id: str
    request: Request
    reference: refs.Original
    evidence: closures.Evidence
    estimated_value: Value | None
    unavailable_reason: Literal["unknown_currency", "missing_rate", "invalid_rate"] | None
    confidence: Literal["declared_rate_scenario_not_agreed_quote"] = "declared_rate_scenario_not_agreed_quote"
    recommended_action: Literal["review_actual_agreement_eligibility_and_recovery_before_action"] = "review_actual_agreement_eligibility_and_recovery_before_action"
    retained: Literal[False] = False
    causal_loss_proven: Literal[False] = False
    action_executed: Literal[False] = False

    @field_validator("retained", "causal_loss_proven", "action_executed", mode="before")
    @classmethod
    def no_claim(cls, value):
        if value is not False:
            raise ValueError("A historical-rate scenario is not a retained quote or causal loss")
        return value


def preview(db, institute, appointment_id, request, actor):
    if not isinstance(actor, str) or not actor or actor != actor.strip() or len(actor) > 160:
        raise business_error("A signed valuation actor is required")
    try:
        request = Request.model_validate(request.model_dump())
    except ValueError as error:
        raise business_error("Explicit historical valuation terms are required") from error
    lock_institute(db, institute)
    appointment = db.scalar(select(Appointment).where(Appointment.institute_id == institute, Appointment.id == appointment_id)
        .execution_options(populate_existing=True))
    if appointment is None:
        raise not_found("Réservation introuvable")
    now = utcnow()
    reference = db.scalar(select(BookingEvent).where(BookingEvent.institute_id == institute, BookingEvent.appointment_id == appointment_id,
        BookingEvent.id == request.reference_event_id).execution_options(populate_existing=True))
    closed = db.scalar(select(BookingEvent).where(BookingEvent.institute_id == institute, BookingEvent.appointment_id == appointment_id,
        BookingEvent.id == request.closure_event_id).execution_options(populate_existing=True))
    try:
        request = Request.model_validate(request.model_dump())
        if reference is None or closed is None or reference.price_reference is None:
            raise ValueError("Explicit owned reference and closure events are required")
        if db.scalar(select(func.count()).select_from(BookingEvent).where(BookingEvent.institute_id == institute,
            BookingEvent.appointment_id == appointment_id, BookingEvent.event_type == "created")) > 1:
            raise ValueError("A unique booking creation is required")
        original = refs.verify(reference, institute, appointment_id, now)
        terms = refs.Terms.model_validate(original.terms)
        closed_at = explicit_utc_instant(closed.occurred_at)
        if original.fingerprint != request.expected_fingerprint or terms.occurred_at > closed_at \
                or terms.service_id != closed.after.get("service_id") or closed_at > now:
            raise ValueError("Historical reference must match selected closure service and chronology")
        if closed_at >= now or db.scalar(select(func.count()).select_from(BookingEvent).where(
            BookingEvent.institute_id == institute, BookingEvent.appointment_id == appointment_id,
            BookingEvent.event_type.in_(["cancelled", "no_show"]))) != 1:
            raise ValueError("One terminal closure observed before the capture is required")
        window = Window(institute_id=institute, start=closed_at, end=now, captured_at=now)
        evidence = closures.Evidence(institute_id=institute, event_id=closed.id, appointment_id=appointment_id,
            event_type=closed.event_type, actor_id=closed.actor_id, occurred_at=closed_at, captured_at=now, before=closed.before, after=closed.after)
        closures.verify(evidence, closures.BookingSnapshot.model_validate(snapshot(appointment)), window)
        quality, amount = getattr(terms, request.rate+"_quality"), getattr(terms, request.rate+"_minor")
        reason = "unknown_currency" if terms.currency is None else "missing_rate" if quality == "missing" else "invalid_rate" if quality == "invalid" else None
        return Preview(actor_id=actor, request=request, reference=original, evidence=evidence,
            estimated_value=Value(currency=terms.currency, amount_minor=amount) if reason is None else None, unavailable_reason=reason)
    except (ValueError, TypeError, KeyError, OverflowError) as error:
        raise business_error("Historical closure valuation sources require verification") from error
