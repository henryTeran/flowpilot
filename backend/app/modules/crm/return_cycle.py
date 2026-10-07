"""Recorded care return intervals; neither physical visits nor booking credits."""
from typing import Iterable, Literal
from pydantic import AwareDatetime, model_validator
from app.modules.crm.metrics import BillingWindow, Count, ExactRatio, Fact, Identifier, Unsigned, microseconds


class CompletedCareFact(Fact):
    institute_id: Identifier
    customer_id: Identifier
    ticket_id: Identifier
    source_kind: Literal["session", "appointment"]
    source_id: Identifier
    service_id: Identifier
    actual_start_at: AwareDatetime
    actual_end_at: AwareDatetime
    captured_at: AwareDatetime

    @model_validator(mode="after")
    def chronology(self):
        if not self.actual_start_at < self.actual_end_at <= self.captured_at:
            raise ValueError("A completed care source requires coherent actual instants")
        return self


class CareEpisode(Fact):
    ticket_id: Identifier
    started_at: AwareDatetime
    completed_at: AwareDatetime
    execution_count: Count
    service_ids: tuple[Identifier, ...]


class ReturnGap(Fact):
    previous_ticket_id: Identifier
    next_ticket_id: Identifier
    gap_us: Unsigned | None
    quality: Literal["known", "overlapping_episodes"]


class RecordedReturnCycle(Fact):
    window: BillingWindow
    basis: Literal["recorded_completed_ticket_care"] = "recorded_completed_ticket_care"
    execution_count: Count
    episode_count: Count
    known_gap_count: Count
    overlapping_gap_count: Count
    known_gap_total_us: Unsigned
    average_return_gap_us: ExactRatio | None
    episodes: tuple[CareEpisode, ...]
    gaps: tuple[ReturnGap, ...]
    complete_customer_history: Literal[False] = False
    inferred_booking_credit: Literal[False] = False


def calculate(window: BillingWindow, facts: Iterable[CompletedCareFact]) -> RecordedReturnCycle:
    """Group only explicit shared tickets; do not guess a visit from nearby clocks."""
    sources = set()
    tickets = {}
    for fact in facts:
        if (fact.institute_id != window.institute_id or fact.customer_id != window.customer_id
            or fact.captured_at != window.captured_at):
            raise ValueError("Care source owner and capture must match the observation")
        identity = (fact.source_kind, fact.source_id)
        if identity in sources or not window.start <= fact.actual_end_at < window.end:
            raise ValueError("Care sources must be unique and complete inside the half-open window")
        sources.add(identity)
        group = tickets.setdefault(fact.ticket_id, dict(first=fact.actual_start_at, last=fact.actual_end_at, count=0, services=set()))
        group["first"] = min(group["first"], fact.actual_start_at)
        group["last"] = max(group["last"], fact.actual_end_at)
        group["count"] += 1
        group["services"].add(fact.service_id)
    episodes = tuple(CareEpisode(ticket_id=ticket, started_at=g["first"], completed_at=g["last"],
        execution_count=g["count"], service_ids=tuple(sorted(g["services"])))
        for ticket, g in sorted(tickets.items(), key=lambda item: (item[1]["first"], item[1]["last"], item[0])))
    gaps = []
    known = total = overlapping = 0
    for previous, following in zip(episodes, episodes[1:]):
        delta = microseconds(following.started_at-previous.completed_at)
        if delta < 0:
            overlapping += 1
        else:
            known += 1
            total += delta
        gaps.append(ReturnGap(previous_ticket_id=previous.ticket_id, next_ticket_id=following.ticket_id,
            gap_us=str(delta) if delta >= 0 else None, quality="known" if delta >= 0 else "overlapping_episodes"))
    return RecordedReturnCycle(window=window, execution_count=len(sources), episode_count=len(episodes),
        known_gap_count=known, overlapping_gap_count=overlapping, known_gap_total_us=str(total),
        average_return_gap_us=ExactRatio(numerator=str(total), denominator=str(known)) if known and not overlapping else None,
        episodes=episodes, gaps=tuple(gaps))
