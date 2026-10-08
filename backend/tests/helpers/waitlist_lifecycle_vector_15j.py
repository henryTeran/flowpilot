"""Pure typed lifecycle JSON vectors; no SQL connection or application startup."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
from app.modules.waitlist.domain import Demand
from app.modules.waitlist.originals import Original, Source, Envelope, fingerprint
from app.modules.waitlist.lifecycle import Event, State, Audit

now = datetime(2026, 10, 8, 10, tzinfo=timezone.utc)


def declaration(identifier, customer, minutes=0):
    captured = now+timedelta(minutes=minutes)
    source = Source(customer_id=customer, registered_at=now-timedelta(days=3), service_id="care", duration_minutes=30, allowed_employee_ids=["employee"])
    demand = Demand(institute_id="own", declared_at=captured, customer_id=customer, service_id="care", duration_minutes=30,
        availability=[dict(start=now+timedelta(hours=1), end=now+timedelta(hours=2))], allowed_employee_ids=["employee"],
        constraints_review="confirmed", availability_evidence="Déclaration cliente 😀", constraints_evidence="Contraintes relues")
    original = Original(id=identifier, institute_id="own", actor_id="manager-É", created_at=captured, idempotency_key=f"demand-{identifier}",
        reason=f"Déclaration {identifier}", demand=demand, source=source)
    raw = original.model_dump(mode="json")
    return Envelope(original=raw, fingerprint=fingerprint(raw))


def transition(identifier, root, target, previous, action, minutes):
    event = Event(id=identifier, institute_id="own", actor_id="manager-É", created_at=now+timedelta(minutes=minutes),
        root_id=root.original["id"], root_fingerprint=root.fingerprint,
        previous_id=previous.original["id"] if previous else None, previous_fingerprint=previous.fingerprint if previous else None,
        action=action, target_id=target.original["id"], target_fingerprint=target.fingerprint, reason=f"Action {action} relue\navec preuve 😀",
        idempotency_key=f"event-{identifier}", activation_source=None if action == "cancel" else Source.model_validate(target.original["source"]))
    raw = event.model_dump(mode="json")
    return Envelope(original=raw, fingerprint=fingerprint(raw))


root = declaration("waitlist_demand_000", "customer")
replacement = declaration("waitlist_demand_001", "customer", 2)
activated_event = transition("event_z", root, root, None, "activate", 1)
revised_event = transition("event_a", root, replacement, activated_event, "revise", 3)
# Equal clocks remain ordered by causal predecessor, never event-ID sorting.
cancelled_event = transition("event_b", root, replacement, revised_event, "cancel", 3)
activated = State(root=root, current_demand=root, state="active", events=(activated_event,))
revised = State(root=root, current_demand=replacement, state="active", events=(activated_event, revised_event))
cancelled = State(root=root, current_demand=replacement, state="cancelled", events=(activated_event, revised_event, cancelled_event))
other = declaration("waitlist_demand_002", "other-customer")
other_state = State(root=other, current_demand=other, state="active", events=(transition("event_other", other, other, None, "activate", 1),))
audit = Audit(institute_id="own", captured_at=now+timedelta(minutes=5), offset=0, limit=20, total=2, active=1, cancelled=1, states=(cancelled, other_state))
target = Path(__file__).resolve().parents[3]/"frontend/tests/fixtures/waitlist-lifecycle-15j.json"
target.write_text(json.dumps({name: value.model_dump(mode="json") for name, value in
    dict(audit=audit, activated=activated, revised=revised, cancelled=cancelled).items()}, ensure_ascii=True, indent=2)+"\n", encoding="utf-8")
