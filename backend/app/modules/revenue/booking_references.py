"""Verified, bounded historical catalog references; no implicit rate selection."""
from typing import Annotated, Literal
from pydantic import AwareDatetime, Field, StringConstraints, field_validator, model_validator
from sqlalchemy import select
from app.modules.crm.metrics import Fact, Identifier, Minor, Count
from app.modules.appointments.models import Appointment, BookingEvent
from app.modules.appointments.price_references import fingerprint
from app.modules.revenue.closures import BookingSnapshot
from app.modules.tickets.repository import lock_institute
from app.modules.workforce.schemas import MatrixPage
from app.shared.exceptions import business_error, not_found
from app.shared.time import utcnow, explicit_utc_instant


class Terms(Fact):
    institute_id: Identifier
    appointment_id: Identifier
    event_id: Identifier
    event_type: Literal["created", "modified"]
    occurred_at: AwareDatetime
    actor_id: str | None
    service_id: Identifier
    duration_min: int = Field(strict=True, ge=0)
    duration_max: int | None = Field(ge=0, strict=True)
    currency: Literal["CHF", "EUR"] | None
    currency_settings_at: AwareDatetime | None
    currency_settings_actor_id: str | None
    currency_unavailable_reason: Literal["settings_absent", "settings_clock_missing", "future_settings"] | None
    member_minor: Minor | None
    member_quality: Literal["known", "missing", "invalid"]
    passage_minor: Minor | None
    passage_quality: Literal["known", "missing", "invalid"]
    basis: Literal["catalog_reference_at_booking_service_selection"]
    agreed_quote: Literal[False]
    paid_price: Literal[False]

    @field_validator("agreed_quote", "paid_price", mode="before")
    @classmethod
    def no_claim(cls, value):
        if value is not False:
            raise ValueError("A catalog reference is neither an agreed quote nor paid price")
        return value

    @model_validator(mode="after")
    def coherent(self):
        for rate in ("member", "passage"):
            if (getattr(self, rate+"_quality") == "known") != (getattr(self, rate+"_minor") is not None):
                raise ValueError("Historical rate diagnostics must agree")
        reason, at = self.currency_unavailable_reason, self.currency_settings_at
        if reason is None:
            if self.currency is None or at is None or at > self.occurred_at:
                raise ValueError("A known currency requires observed explicit configuration")
        elif self.currency is not None or reason == "future_settings" and (at is None or at <= self.occurred_at) \
                or reason in {"settings_absent", "settings_clock_missing"} and at is not None \
                or reason == "settings_absent" and self.currency_settings_actor_id is not None:
            raise ValueError("Unlabelled currency must retain its source diagnostic")
        return self


class Original(Fact):
    # Keep source JSON timestamp spellings intact for independent native hashing.
    terms: dict
    fingerprint: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class Read(Fact):
    institute_id: Identifier
    appointment_id: Identifier
    captured_at: AwareDatetime
    page: MatrixPage
    originals: tuple[Original, ...]
    legacy_service_selection_events: Count


def verify(event, institute, appointment, now):
    raw = event.price_reference
    if not isinstance(raw, dict) or set(raw) != {"terms", "fingerprint"} or fingerprint(raw["terms"]) != raw["fingerprint"]:
        raise ValueError("Historical reference fingerprint differs")
    original = Original.model_validate(raw)
    terms = Terms.model_validate(original.terms)
    at = explicit_utc_instant(event.occurred_at)
    if (terms.institute_id, terms.appointment_id, terms.event_id, terms.event_type, terms.occurred_at, terms.actor_id) \
            != (institute, appointment, event.id, event.event_type, at, event.actor_id) or at > now:
        raise ValueError("Historical reference event scope or clock differs")
    after = BookingSnapshot.model_validate(event.after)
    if after.status not in {"scheduled", "confirmed"} or after.service_id != terms.service_id \
            or after.start_time >= after.end_time or after.actual_start_time is not None \
            or after.actual_end_time is not None or after.checkout_ticket_id is not None:
        raise ValueError("Reference requires a retained unexecuted service selection")
    if event.event_type == "created":
        if event.before is not None or after.status != "scheduled":
            raise ValueError("Created reference cannot substitute a predecessor")
    else:
        before = BookingSnapshot.model_validate(event.before)
        if before.status not in {"scheduled", "confirmed"} or before.status != after.status or before.service_id == after.service_id \
                or before.actual_start_time is not None or before.actual_end_time is not None or before.checkout_ticket_id is not None:
            raise ValueError("Modified reference requires an actual service change")
    return original


def read(db, institute, appointment, offset=0, limit=20):
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 50:
        raise business_error("Invalid price reference page bounds")
    lock_institute(db, institute)
    if db.scalar(select(Appointment.id).where(Appointment.institute_id == institute, Appointment.id == appointment)) is None:
        raise not_found("Réservation introuvable")
    now, total, legacy, created, rows = utcnow(), 0, 0, 0, []
    try:
        for event in db.scalars(select(BookingEvent).where(BookingEvent.institute_id == institute, BookingEvent.appointment_id == appointment)
            .order_by(BookingEvent.occurred_at, BookingEvent.id).execution_options(yield_per=100, populate_existing=True)):
            if explicit_utc_instant(event.occurred_at) > now:
                raise ValueError("Future booking events are not observed history")
            created += event.event_type == "created"
            if created > 1:
                raise ValueError("A booking cannot have two creation events")
            if event.price_reference is None:
                if event.event_type == "created" or event.event_type == "modified" and isinstance(event.before, dict) \
                        and isinstance(event.after, dict) and event.before.get("service_id") != event.after.get("service_id"):
                    legacy += 1
                continue
            original = verify(event, institute, appointment, now)
            if offset <= total < offset+limit:
                rows.append(original)
            total += 1
    except (ValueError, TypeError, KeyError) as error:
        raise business_error("Historical booking price references require verification") from error
    return Read(institute_id=institute, appointment_id=appointment, captured_at=now,
        page=MatrixPage(offset=offset, limit=limit, total=total), originals=tuple(rows), legacy_service_selection_events=legacy)
