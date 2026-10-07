"""Pure internal ledger decisions; uncertainty never becomes cancellation proof."""
from datetime import timezone
from hashlib import sha256
import json
from typing import Literal
from pydantic import AwareDatetime, model_validator
from app.modules.crm.event_candidates import EventCandidate
from app.modules.crm.event_sources import EventSourceRead
from app.modules.crm.metrics import Fact, Identifier


def identity(candidate: EventCandidate) -> str:
    source = candidate.source
    # Renewed expiry terms are distinct occurrences. Balance, policy correction,
    # capture clock and care-clock correction do not duplicate an occurrence.
    term = source.expires_at.astimezone(timezone.utc).isoformat() if source.source_kind in {"package", "membership"} else None
    parts = [candidate.institute_id,candidate.customer_id,candidate.rule.trigger,source.source_kind,source.source_id,term]
    return sha256(json.dumps(parts,separators=(",",":"),ensure_ascii=True).encode()).hexdigest()


class EventDecision(Fact):
    event_key: Identifier
    candidate: EventCandidate
    state: Literal["scheduled", "due", "blocked", "cancelled", "expired", "processed"]
    reason: Literal["candidate", "source_uncertain", "rule_disabled", "package_exhausted", "occurrence_expired",
                    "superseded", "birthday_declared_unknown", "explicit_cancellation", "already_processed"]
    evaluated_at: AwareDatetime

    @model_validator(mode="after")
    def coherent_decision(self):
        allowed = {"scheduled":{"candidate"},"due":{"candidate"},"blocked":{"source_uncertain"},
            "expired":{"occurrence_expired"},"processed":{"already_processed"},
            "cancelled":{"rule_disabled","package_exhausted","superseded","birthday_declared_unknown","explicit_cancellation"}}
        c = self.candidate
        if (self.event_key != identity(c) or self.reason not in allowed[self.state]
            or (c.source.institute_id,c.source.customer_id) != (c.institute_id,c.customer_id)
            or c.captured_at > self.evaluated_at):
            raise ValueError("Event identity, owned source, state/reason and chronology must agree")
        return self


def reconcile(capture: EventSourceRead, previous: tuple[EventDecision, ...]) -> tuple[EventDecision, ...]:
    owner = (capture.institute_id,capture.customer_id)
    keys = set()
    for old in previous:
        EventDecision.model_validate(old.model_dump())
        if ((old.candidate.institute_id,old.candidate.customer_id) != owner or old.event_key != identity(old.candidate)
            or old.event_key in keys or old.evaluated_at > capture.captured_at):
            raise ValueError("Unique owned prior events and monotonic capture required")
        keys.add(old.event_key)
    fresh = {}
    for candidate in capture.candidates:
        key = identity(candidate)
        if ((candidate.institute_id,candidate.customer_id) != owner or candidate.captured_at != capture.captured_at
            or (candidate.source.institute_id,candidate.source.customer_id) != owner or key in fresh):
            raise ValueError("Unique owned candidates from this capture required")
        fresh[key] = candidate
    old_by_key = {old.event_key:old for old in previous}
    result = []
    for key in sorted(set(fresh)|set(old_by_key)):
        old = old_by_key.get(key); current = fresh.get(key)
        # Explicit cancellation and successful internal processing are terminal.
        if old and (old.reason == "explicit_cancellation" or old.state == "processed"):
            result.append(old); continue
        candidate = current or old.candidate
        state,reason = "blocked","source_uncertain"
        if current:
            state,reason = current.state,"candidate"
            if state == "disabled": state,reason = "cancelled","rule_disabled"
            elif state == "exhausted": state,reason = "cancelled","package_exhausted"
            elif state == "expired": reason = "occurrence_expired"
        else:
            replacements = [v for v in fresh.values() if v.rule.trigger == candidate.rule.trigger]
            same_source = any((v.source.source_kind,v.source.source_id) == (candidate.source.source_kind,candidate.source.source_id) for v in replacements)
            if same_source or (candidate.rule.trigger in {"rebooking","inactivity"} and replacements):
                state,reason = "cancelled","superseded"
            elif candidate.rule.trigger == "birthday" and capture.lifecycle.birthday and capture.lifecycle.birthday.reason == "birthday_unknown":
                state,reason = "cancelled","birthday_declared_unknown"
        result.append(EventDecision(event_key=key,candidate=candidate,state=state,reason=reason,evaluated_at=capture.captured_at))
    return tuple(result)
