"""Bounded internal event processing selection, without any message transport."""
from datetime import timezone
from app.modules.crm.event_reconciliation import EventDecision

BATCH_SIZE = 20  # Operational work bound, not a commercial/calendar default.


def processing_keys(decisions: tuple[EventDecision, ...]) -> set[str]:
    eligible = sorted((d for d in decisions if d.state == "due"),
        key=lambda d: (d.candidate.due_at.astimezone(timezone.utc),d.event_key))
    return {d.event_key for d in eligible[:BATCH_SIZE]}
