"""Aggregate existing closure evidence without inferring causal financial loss."""
from typing import Literal
from pydantic import AwareDatetime
from app.modules.crm.metrics import Fact, Count, Identifier
from app.modules.revenue import closures, walk_in_cancellations, billing
from app.modules.waitlist.originals import fingerprint


class BookingSummary(Fact):
    window: billing.Window
    source_digest: str
    cancelled_count: Count
    no_show_count: Count
    unpriced_count: Count
    institute_terminal_bookings_without_closure_event: Count


class WalkInSummary(Fact):
    window: billing.Window
    source_digest: str
    retained_terms_count: Count
    legacy_unpriced_count: Count
    retained_amounts: tuple[billing.AmountGroup, ...]


class Read(Fact):
    institute_id: Identifier
    captured_at: AwareDatetime
    bookings: BookingSummary
    walk_ins: WalkInSummary
    causal_loss_proven: Literal[False] = False
    complete_history: Literal[False] = False
    financial_loss: None = None
    basis: Literal["recorded_closure_events_not_causal_financial_loss"] = "recorded_closure_events_not_causal_financial_loss"


def read(db, institute, start, end):
    # Both original readers retain the same institute lock in this transaction;
    # their separate observation clocks remain explicit rather than rewritten.
    bookings = closures.read(db, institute, start, end)
    walk_ins = walk_in_cancellations.read(db, institute, start, end)
    return Read(institute_id=institute, captured_at=max(bookings.window.captured_at, walk_ins.window.captured_at),
        bookings=BookingSummary(window=bookings.window, source_digest=fingerprint(bookings.model_dump(mode="json")),
            **bookings.model_dump(include={"cancelled_count", "no_show_count", "unpriced_count", "institute_terminal_bookings_without_closure_event"})),
        walk_ins=WalkInSummary(window=walk_ins.window, source_digest=fingerprint(walk_ins.model_dump(mode="json")),
            **walk_ins.model_dump(include={"retained_terms_count", "legacy_unpriced_count", "retained_amounts"})))
