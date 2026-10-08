"""Typed current matching vectors, using the sovereign pure matching kernel.

No SQL connection, application startup or mutable source capture is performed.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
from app.modules.waitlist import domain, lifecycle, sources, detection, originals
from app.modules.crm.lifecycle_originals import Original as PermissionOriginal

target = Path(__file__).resolve().parents[3] / "frontend/tests/fixtures/waitlist-matching-15l.json"
states = json.loads((target.parent / "waitlist-lifecycle-15j.json").read_text(encoding="utf-8"))
state = lifecycle.State.model_validate(states["revised"])
cancelled = lifecycle.State.model_validate(states["cancelled"])
now = datetime(2026, 10, 8, 10, 5, tzinfo=timezone.utc)
horizon = now + timedelta(hours=3)
demand = domain.Demand.model_validate(state.current_demand.original["demand"])
policy = sources.Policy(channel="email", history_requirement="review_only", permission_requirement="review_only")
capture = domain.Capture(institute_id="own", captured_at=now,
    service=domain.ServiceCapacity(service_id="care", duration_minutes=30, required_skills=["qualified"],
        needs=[dict(kind="room", capability="clean", quantity=1), dict(kind="room", capability="special", quantity=1)], resource_configuration="known"),
    employees=[domain.EmployeeCapacity(employee_id="employee", skills=["qualified"], state="known", windows=[dict(start=now, end=horizon)])],
    resources=[domain.ResourceCapacity(resource_id="room-flex", kind="room", capabilities=["clean", "special"], state="active_known", reservations=[]),
        domain.ResourceCapacity(resource_id="room-clean", kind="room", capabilities=["clean"], state="active_known", reservations=[])],
    customer=domain.CustomerContext(customer_id="customer", history="no_recorded_care", history_reference=None, history_at=None,
        permission="unknown", channel="email", permission_at=None, permission_reference=None))
evidence = sources.Evidence(registered_at=now-timedelta(days=3), latest_care=None, observed_care_episodes=0,
    care_diagnostics=dict(unlinked_ticket=0, invalid_owner_or_service=0, invalid_actual_times=0),
    permission_original=None, permission_reason="declaration_absent", employee_reasons={"employee": "available"},
    customer_booking_ids=[], customer_session_ids=[], waiting_tickets=0, queue_slots=[], unprojectable_queue_tickets=0)


def read(cap=capture, proof=evidence, rules=policy, reason=None, selected=state):
    return sources.Read(state=selected, captured_at=now, horizon_end=horizon, policy=rules,
        review=None if reason else domain.match(demand, cap), evidence=proof, unavailable_reason=reason)


cases = dict(options=read(), duration_changed=read(capture.model_copy(update={"service": capture.service.model_copy(update={"duration_minutes": 45})})),
    queue_unknown=read(capture.model_copy(update={"queue_capacity": "unknown"}), evidence.model_copy(update={"waiting_tickets": 1, "unprojectable_queue_tickets": 1})),
    history_refused=read(rules=policy.model_copy(update={"history_requirement": "observed_care_required"}), reason="history_requirement_unmet"),
    permission_refused=read(rules=policy.model_copy(update={"permission_requirement": "recorded_grant_required"}), reason="permission_requirement_unmet"),
    cancelled=read(proof=None, selected=cancelled, reason="cancelled"), registration_unavailable=read(proof=None, reason="registration_unavailable"))
care = dict(ticket_id="observed-ticket", started_at=now-timedelta(days=1, minutes=30), completed_at=now-timedelta(days=1), execution_count=1, service_ids=["care"])
permission = PermissionOriginal(id="permission-1", institute_id="own", customer_id="customer", actor_id="manager", created_at=now-timedelta(hours=1),
    previous_id=None, reason="Explicit channel decision", idempotency_key="permission-key", declaration=dict(institute_id="own", customer_id="customer",
        birthday=None, birthday_evidence=None, communications=[dict(channel=channel, purpose=purpose, permission="granted" if channel == "email" and purpose == "service_follow_up" else "unknown",
            evidence="Confirmed by customer" if channel == "email" and purpose == "service_follow_up" else None)
            for channel in ("email", "sms") for purpose in ("service_follow_up", "marketing")]))
observed = domain.CustomerContext(customer_id="customer", history="observed", history_reference="observed-ticket", history_at=care["completed_at"],
    permission="granted", channel="email", permission_at=permission.created_at, permission_reference=permission.id)
cases["observed_granted"] = read(capture.model_copy(update={"customer": observed}), evidence.model_copy(update={
    "latest_care": sources.CareEpisode.model_validate(care), "observed_care_episodes": 1, "permission_original": permission, "permission_reason": "current_declaration"}),
    policy.model_copy(update={"history_requirement": "observed_care_required", "permission_requirement": "recorded_grant_required"}))
slot = sources.QueueSlot(ticket_id="queued-ticket", employee_id="employee", start=now, end=now+timedelta(minutes=30), resource_ids=["room-clean"])
queued_capture = capture.model_copy(update={"employees": (capture.employees[0].model_copy(update={"windows": (domain.Window(start=slot.end, end=horizon),)}),),
    "resources": (capture.resources[0], capture.resources[1].model_copy(update={"reservations": (domain.Window(start=slot.start, end=slot.end),)}))})
cases["queue_known"] = read(queued_capture, evidence.model_copy(update={"waiting_tickets": 1, "queue_slots": (slot,)}))
result = {k: sources.Read.model_validate(v.model_dump()).model_dump(mode="json") for k, v in cases.items()}
result["detection"] = detection.Detection(institute_id="own", captured_at=now, horizon_end=horizon, policy=policy, offset=0, limit=20,
    examined_roots=2, active=1, cancelled=1, with_options=1, without_options=0, unavailable_reasons={}, reviews=(cases["options"],)).model_dump(mode="json")
cohort = []
for n in range(25):
    raw = state.model_dump(mode="json")
    for field, suffix in (("root", "root"), ("current_demand", "target")):
        original = raw[field]["original"]
        original["id"] = f"waitlist_demand_{n:03d}_{suffix}"
        original["idempotency_key"] = f"demand-{n}-{suffix}"
        raw[field]["fingerprint"] = originals.fingerprint(original)
    previous = None
    for step, event in enumerate(raw["events"]):
        original = event["original"]
        target_proof = raw["root"] if step == 0 else raw["current_demand"]
        original.update(id=f"event-{n}-{step}", idempotency_key=f"event-key-{n}-{step}", root_id=raw["root"]["original"]["id"],
            root_fingerprint=raw["root"]["fingerprint"], target_id=target_proof["original"]["id"], target_fingerprint=target_proof["fingerprint"],
            previous_id=previous["original"]["id"] if previous else None, previous_fingerprint=previous["fingerprint"] if previous else None)
        event["fingerprint"] = originals.fingerprint(original)
        previous = event
    selected = lifecycle.State.model_validate(raw)
    cohort.append(read(selected=selected) if n else read(capture.model_copy(update={"queue_capacity": "unknown"}),
        evidence.model_copy(update={"waiting_tickets": 1, "unprojectable_queue_tickets": 1}), selected=selected))
for offset in (0, 20, 40):
    result[f"detection_{offset}"] = detection.Detection(institute_id="own", captured_at=now, horizon_end=horizon, policy=policy, offset=offset, limit=20,
        examined_roots=28, active=25, cancelled=3, with_options=24, without_options=1, unavailable_reasons={"queue_projection_unknown": 1},
        reviews=tuple(cohort[offset:offset+20])).model_dump(mode="json")
target.write_text(json.dumps(result, ensure_ascii=True, indent=2)+"\n", encoding="utf-8")
