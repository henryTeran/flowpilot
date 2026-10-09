"""Minimal projection of existing institute-wide rebooking opportunities."""
from typing import Literal
from pydantic import AwareDatetime, Field, model_validator, field_validator
from app.modules.base.read_capabilities import Digest
from app.modules.crm.metrics import Fact, Count, Identifier
from app.modules.crm.event_candidates import EventCandidate
from app.modules.revenue import rebooking, closures, walk_in_cancellations
from app.modules.copilot.losses import BookingSummary, WalkInSummary
from app.modules.waitlist.originals import fingerprint


class Returns(Fact):
    institute_id: Identifier
    captured_at: AwareDatetime
    source_digest: Digest
    source: Literal["observed_care_declared_rebooking_rule"] = "observed_care_declared_rebooking_rule"
    total_candidates: Count
    examined_customers: Count
    already_booked_customers: Count
    scheduled_customers: Count
    disabled_customers: Count
    no_candidate_customers: Count
    diagnostics: dict[str, Count]
    candidates: tuple[EventCandidate, ...]
    page_limit: Literal[20] = 20
    estimated_value: None = None
    delivery_authorized: Literal[False] = False
    action_executed: Literal[False] = False
    complete_customer_history: Literal[False] = False

    @model_validator(mode="after")
    def coherent_candidates(self):
        if len(self.candidates) != min(self.total_candidates, self.page_limit):
            raise ValueError("First-page candidates must match total and page bound")
        if len({row.customer_id for row in self.candidates}) != len(self.candidates):
            raise ValueError("At most one rebooking opportunity per customer")
        for row in self.candidates:
            if (row.institute_id != self.institute_id or row.captured_at != self.captured_at
                or row.state != "due" or row.rule.trigger != "rebooking"
                or row.source.source_kind != "care_episode" or row.source.institute_id != self.institute_id
                or row.source.customer_id != row.customer_id):
                raise ValueError("Own due rebooking sources and capture required")
        return self


def read_returns(db, institute):
    source = rebooking.read(db, institute)
    return Returns(institute_id=institute, captured_at=source.captured_at,
        source_digest=fingerprint(source.model_dump(mode="json")), total_candidates=source.page.total,
        candidates=tuple(row.candidate for row in source.opportunities), **source.model_dump(include={
            "examined_customers", "already_booked_customers", "scheduled_customers", "disabled_customers",
            "no_candidate_customers", "diagnostics"}))


class BookingFollowUp(Fact):
    event_id: Identifier
    appointment_id: Identifier
    type: Literal["review_cancelled_booking", "review_no_show_booking"]
    occurred_at: AwareDatetime
    estimated_value: None = None


class WalkInFollowUp(Fact):
    event_id: int = Field(strict=True, gt=0)
    ticket_id: Identifier
    type: Literal["review_cancelled_walk_in"] = "review_cancelled_walk_in"
    occurred_at: AwareDatetime
    retained_value: walk_in_cancellations.Value | None
    confidence: Literal["retained_commercial_terms_not_causal_loss", "legacy_cancellation_unpriced"]


class FollowUps(Fact):
    institute_id: Identifier
    captured_at: AwareDatetime
    source: Literal["recorded_closure_follow_up"] = "recorded_closure_follow_up"
    bookings: BookingSummary
    walk_ins: WalkInSummary
    booking_total: Count
    walk_in_total: Count
    booking_candidates: tuple[BookingFollowUp, ...]
    walk_in_candidates: tuple[WalkInFollowUp, ...]
    page_limit_per_source: Literal[20] = 20
    estimated_recovered_revenue: None = None
    causal_loss_proven: Literal[False] = False
    delivery_authorized: Literal[False] = False
    action_executed: Literal[False] = False
    complete_history: Literal[False] = False

    @field_validator("causal_loss_proven", "delivery_authorized", "action_executed", "complete_history", mode="before")
    @classmethod
    def no_authority(cls, value):
        if value is not False:
            raise ValueError("A follow-up read cannot grant authority or prove recovery")
        return value

    @model_validator(mode="after")
    def coherent_sources(self):
        windows = (self.bookings.window, self.walk_ins.window)
        if any(window.institute_id != self.institute_id for window in windows) or self.captured_at != max(window.captured_at for window in windows):
            raise ValueError("Own source windows and their latest capture required")
        if windows[0].start != windows[1].start or windows[0].end != windows[1].end:
            raise ValueError("Both sources must cover the selected period")
        for rows, total, window in ((self.booking_candidates, self.booking_total, windows[0]),
                                   (self.walk_in_candidates, self.walk_in_total, windows[1])):
            if len(rows) != min(total, self.page_limit_per_source) or len({row.event_id for row in rows}) != len(rows):
                raise ValueError("Unique first-page events must match the source total")
            if any(not window.start <= row.occurred_at < window.end or row.occurred_at > window.captured_at for row in rows):
                raise ValueError("Follow-up events must belong to their observed window")
        if self.booking_total != self.bookings.cancelled_count + self.bookings.no_show_count or self.walk_in_total != self.walk_ins.retained_terms_count + self.walk_ins.legacy_unpriced_count:
            raise ValueError("Follow-up totals must match the original aggregate counts")
        return self


def read_follow_ups(db, institute, start, end):
    bookings = closures.read(db, institute, start, end)
    walk_ins = walk_in_cancellations.read(db, institute, start, end)
    return FollowUps(institute_id=institute, captured_at=max(bookings.window.captured_at, walk_ins.window.captured_at),
        bookings=BookingSummary(window=bookings.window, source_digest=fingerprint(bookings.model_dump(mode="json")),
            **bookings.model_dump(include={"cancelled_count", "no_show_count", "unpriced_count", "institute_terminal_bookings_without_closure_event"})),
        walk_ins=WalkInSummary(window=walk_ins.window, source_digest=fingerprint(walk_ins.model_dump(mode="json")),
            **walk_ins.model_dump(include={"retained_terms_count", "legacy_unpriced_count", "retained_amounts"})),
        booking_total=bookings.page.total, walk_in_total=walk_ins.page.total,
        booking_candidates=tuple(BookingFollowUp(event_id=row.evidence.event_id, appointment_id=row.evidence.appointment_id,
            type=row.type, occurred_at=row.evidence.occurred_at) for row in bookings.opportunities),
        walk_in_candidates=tuple(WalkInFollowUp(event_id=row.evidence.event_id, ticket_id=row.evidence.ticket_id,
            occurred_at=row.evidence.occurred_at, retained_value=row.estimated_value,
            confidence=row.confidence) for row in walk_ins.opportunities))
