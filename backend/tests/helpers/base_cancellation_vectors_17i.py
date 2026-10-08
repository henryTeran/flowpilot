"""Typed synthetic BASE DTO/hash vectors; no SQL or application startup proof."""
import json
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
from app.modules.base import read_capabilities as base, sensitive_capabilities as sensitive, sensitive_originals as operations, approvals, executions
from app.modules.waitlist.originals import Envelope, fingerprint

now = datetime(2026, 10, 8, 13, tzinfo=timezone.utc)
principal = base.Principal(actor_id="signed-manager", institute_id="own", role="responsable_institut")
snapshot = sensitive.Snapshot(status="scheduled", employee_id="employee", service_id="service", customer_id=None,
    start_time=now+timedelta(hours=1), end_time=now+timedelta(hours=1, minutes=30),
    booked_start_time=now+timedelta(hours=1), booked_end_time=now+timedelta(hours=1, minutes=30),
    actual_start_time=None, actual_end_time=None, checkout_ticket_id=None).model_dump(mode="json")
history = fingerprint([{"id": "synthetic-created-event", "after": snapshot}])
preview = sensitive.Preview(principal=principal, capability=sensitive.REGISTRY["APPOINTMENT_CANCEL"], appointment_id="appointment",
    captured_at=now, appointment=snapshot, booking_events=1, booking_history_fingerprint=history,
    state_fingerprint=sensitive.state_digest("own", "appointment", snapshot, 1, history))
operation = operations.Original(capability="APPOINTMENT_CANCEL", selection={"appointment_id": "appointment"},
    expected_state_fingerprint=preview.state_fingerprint, valid_until=now+timedelta(minutes=10),
    reason="Annulation préparée — état examiné", idempotency_key="operation-key", id="operation",
    institute_id="own", actor_id="signed-manager", created_at=now+timedelta(microseconds=1), preview=preview)
def envelope(value):
    raw = value.model_dump(mode="json")
    return Envelope(original=raw, fingerprint=fingerprint(raw))
op = envelope(operation)
decision = approvals.Original(operation_id=op.original["id"], operation_fingerprint=op.fingerprint,
    previous_id=None, previous_fingerprint=None, decision="approve", reason="Décision explicite",
    idempotency_key="approve-key", id="z-approval", institute_id="own", actor_id="other-manager",
    created_at=now+timedelta(microseconds=3), source_checked_at=now+timedelta(microseconds=2), checked_state_fingerprint=preview.state_fingerprint)
approval = envelope(decision)
revocation = envelope(approvals.Original(operation_id=operation.id, operation_fingerprint=op.fingerprint,
    previous_id=decision.id, previous_fingerprint=approval.fingerprint, decision="revoke", reason="Révocation explicite",
    idempotency_key="revoke-key", id="a-revocation", institute_id="own", actor_id="signed-manager",
    created_at=decision.created_at, source_checked_at=None, checked_state_fingerprint=None))
decline = envelope(approvals.Original(operation_id=operation.id, operation_fingerprint=op.fingerprint,
    previous_id=None, previous_fingerprint=None, decision="decline", reason="Refus explicite",
    idempotency_key="decline-key", id="decline", institute_id="own", actor_id="signed-manager",
    created_at=now+timedelta(microseconds=3), source_checked_at=None, checked_state_fingerprint=None))
before = sensitive.Preview(**{**preview.model_dump(), "captured_at": now+timedelta(microseconds=5)})
event = dict(id="synthetic-cancel-event", institute_id="own", appointment_id="appointment", event_type="cancelled",
    actor_id="signed-manager", occurred_at=(now+timedelta(microseconds=6)).isoformat(), before=snapshot,
    after={**snapshot, "status": "cancelled"}, price_reference=None)
execution = envelope(executions.Original(operation_id=operation.id, operation_fingerprint=op.fingerprint,
    approval_id=decision.id, approval_fingerprint=approval.fingerprint, reason="Exécution explicite", idempotency_key="execution-key",
    id="execution", institute_id="own", actor_id="signed-manager", created_at=now+timedelta(microseconds=7),
    before=before, after=event["after"], booking_event_id=event["id"], booking_event_fingerprint=fingerprint(event)))
def state(decisions, status, expired=False):
    return approvals.State(operation=op, captured_at=now+timedelta(minutes=20) if expired else now+timedelta(microseconds=10),
        decisions=decisions, status=status, expired=expired).model_dump(mode="json")
result = {"preview": preview.model_dump(mode="json"), "operation": op.model_dump(mode="json"),
    "approved": state([approval], "approved"), "expired": state([approval], "approved", True),
    "pending": state([], "pending"), "revoked": state([approval, revocation], "revoked"),
    "declined": state([decline], "declined"), "execution": execution.model_dump(mode="json")}
Path(sys.argv[1]).write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
