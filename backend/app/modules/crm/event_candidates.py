"""Pure source-grounded internal event candidates; no persistence or delivery."""
from datetime import timedelta, timezone
from typing import Annotated, Literal
from pydantic import AwareDatetime, Field, model_validator
from app.modules.crm.automation_policy import AutomationPolicy, AutomationRule
from app.modules.crm.metrics import Fact, Identifier
from app.modules.crm.segments import RegisteredCustomerFact


class EventAnchor(Fact):
    institute_id: Identifier
    customer_id: Identifier
    source_id: Identifier
    source_kind: Literal["care_episode", "package", "membership", "birthday"]
    occurred_at: AwareDatetime
    expires_at: AwareDatetime | None
    remaining: Annotated[int, Field(strict=True, ge=0)] | None

    @model_validator(mode="after")
    def coherent_source(self):
        start = self.occurred_at.astimezone(timezone.utc)
        end = self.expires_at.astimezone(timezone.utc) if self.expires_at else None
        if self.source_kind in {"package", "membership", "birthday"}:
            if end is None or end <= start:
                raise ValueError("An explicit positive source term is required")
        elif end is not None:
            raise ValueError("Completed care has no expiry term")
        if (self.source_kind == "package") != (self.remaining is not None):
            raise ValueError("Only a package carries an explicit remaining balance")
        return self


class EventCandidate(Fact):
    institute_id: Identifier
    customer_id: Identifier
    policy_original_id: Identifier
    rule: AutomationRule
    source: EventAnchor
    due_at: AwareDatetime
    valid_until: AwareDatetime | None
    captured_at: AwareDatetime
    state: Literal["scheduled", "due", "expired", "exhausted", "disabled"]
    external_message_sent: Literal[False] = False
    delivery_authorized: Literal[False] = False


def candidates(policy: AutomationPolicy, policy_original_id: str,
               customer: RegisteredCustomerFact, captured_at: AwareDatetime,
               sources: tuple[EventAnchor, ...]) -> tuple[EventCandidate, ...]:
    """Care inactivity/rebooking use latest observed completion, never guessed history.

    Birthday anchors must be supplied from a verified declaration/calendar read;
    care anchors from grouped actual completions; package/membership anchors from
    their explicit terms. Missing anchors produce no invented candidate. Durable
    capture will retain missing-source diagnostics separately.
    """
    captured = captured_at.astimezone(timezone.utc)
    registered = customer.created_at.astimezone(timezone.utc)
    if policy.institute_id != customer.institute_id or registered > captured:
        raise ValueError("Own registered customer and coherent capture required")
    unique = set()
    for source in sources:
        identity = (source.source_kind, source.source_id)
        if (source.institute_id != customer.institute_id or source.customer_id != customer.customer_id
            or identity in unique or (source.source_kind != "birthday" and source.occurred_at.astimezone(timezone.utc) < registered)):
            raise ValueError("Unique own-customer source chronology required")
        # Birthday occurrence can be upcoming; all other source anchors are observed facts.
        if source.source_kind != "birthday" and source.occurred_at.astimezone(timezone.utc) > captured:
            raise ValueError("Future source is not an observed anchor")
        unique.add(identity)
    care = [s for s in sources if s.source_kind == "care_episode"]
    latest = max(care, key=lambda s: (s.occurred_at.astimezone(timezone.utc), s.source_id), default=None)
    result = []
    for rule in policy.rules:
        kind = {"birthday": "birthday", "post_service": "care_episode", "rebooking": "care_episode",
                "inactivity": "care_episode", "package_expiry": "package", "subscription_renewal": "membership"}[rule.trigger]
        selected = [s for s in sources if s.source_kind == kind]
        if rule.trigger in {"rebooking", "inactivity"}:
            selected = [latest] if latest else []
        for source in sorted(selected, key=lambda s: s.source_id):
            start = source.occurred_at.astimezone(timezone.utc)
            end = source.expires_at.astimezone(timezone.utc) if source.expires_at else None
            try:
                offset = timedelta(microseconds=rule.offset_us)
                due = end - offset if rule.trigger in {"package_expiry", "subscription_renewal"} else start + offset
            except OverflowError as error:
                raise ValueError("Event timing lies outside the supported UTC calendar") from error
            # Anticipation cannot authorize a time before the recorded source exists.
            due = max(start, due)
            state = "scheduled" if captured < due else "due"
            if end is not None and captured >= end:
                state = "expired"
            if source.source_kind == "package" and source.remaining == 0:
                state = "exhausted"
            if not rule.enabled:
                state = "disabled"
            result.append(EventCandidate(institute_id=customer.institute_id,customer_id=customer.customer_id,
                policy_original_id=policy_original_id,rule=rule,source=source,due_at=due,
                valid_until=end,captured_at=captured,state=state))
    return tuple(result)
