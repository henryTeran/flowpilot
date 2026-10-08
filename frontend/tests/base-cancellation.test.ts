import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { revenueOriginalFingerprint as hash } from "../src/revenue-scenario-utils";
import { validBasePreview, validBaseOperationEnvelope, validBaseDecisionEnvelope, validBaseApprovalState,
  validBaseExecutionEnvelope, validBaseOperationRequest, validBaseDecisionRequest, validBaseExecutionRequest,
  type BaseApprovalState } from "../src/base-cancellation-utils";
const fixture = JSON.parse(readFileSync(new URL("./fixtures/base-cancellation-17i.json", import.meta.url), "utf8"));
const copy = (v: any) => structuredClone(v);
async function rehash(v: any) { v.fingerprint = await hash(v.original); return v; }

test("typed backend synthetic vectors retain full hashes, Unicode and exact microsecond causal clocks", async () => {
  assert.equal(await validBasePreview(fixture.preview, "own", "appointment"), true);
  assert.equal(await validBaseOperationEnvelope(fixture.operation, "own"), true);
  for (const name of ["approved", "expired", "pending", "revoked", "declined"]) {
    assert.equal(await validBaseApprovalState(fixture[name], "own", fixture.operation), true, name);
  }
  assert.equal(await validBaseDecisionEnvelope(fixture.approved.decisions[0], "own", fixture.operation), true);
  assert.equal(await validBaseExecutionEnvelope(fixture.execution, "own", fixture.approved), true);
  assert.equal(await validBaseExecutionEnvelope(fixture.execution, "own", fixture.expired), true);
  assert.equal(await validBaseExecutionEnvelope(fixture.execution, "own", fixture.revoked), false);
  assert.equal(await validBaseExecutionEnvelope(fixture.execution, "own", fixture.pending), false);
});

test("preview refuses wrong scope, target, registry authority, shape and rehashed state disagreement", async () => {
  assert.equal(await validBasePreview(fixture.preview, "foreign"), false);
  assert.equal(await validBasePreview(fixture.preview, "own", "another"), false);
  for (const attack of [
    (v: any) => { v.principal.role = "accueil"; }, (v: any) => { v.capability.public_execution = true; },
    (v: any) => { v.capability.approval = "approved"; }, (v: any) => { v.approved = true; },
    (v: any) => { v.appointment.employee_id = "invented"; }, (v: any) => { v.booking_events++; },
    (v: any) => { v.appointment.end_time = v.appointment.start_time; }, (v: any) => { v.appointment.notes = "private"; },
    (v: any) => { v.appointment.start_time = "2026-10-08T15:00:00+02:00"; },
    (v: any) => { v.booking_events = Number.MAX_SAFE_INTEGER+1; },
  ]) { const value = copy(fixture.preview); attack(value); assert.equal(await validBasePreview(value, "own"), false); }
});

test("operation refuses full snapshot tamper, forged binding and invalid expiry even after outer rehash", async () => {
  for (const attack of [
    (v: any) => { v.original.reason += "changed"; }, (v: any) => { v.original.actor_id = "invented"; },
    (v: any) => { v.original.selection.appointment_id = "invented"; },
    (v: any) => { v.original.valid_until = v.original.created_at; },
    (v: any) => { v.original.created_at = v.original.preview.captured_at.replace("00Z", "00.000001Z"); v.original.preview.captured_at = "2026-10-08T13:00:00.000002Z"; },
    (v: any) => { v.original.effect = "approved"; },
  ]) {
    const value = copy(fixture.operation); attack(value);
    assert.equal(await validBaseOperationEnvelope(value, "own"), false);
    if (!String(value.original.reason).endsWith("changed")) {
      await rehash(value); assert.equal(await validBaseOperationEnvelope(value, "own"), false);
    }
  }
});

test("complete decision chain rejects branch, reverse order, stale references, clock drift and false status", async () => {
  for (const attack of [
    (v: any) => { v.decisions.reverse(); }, (v: any) => { v.decisions.push(copy(v.decisions[0])); },
    (v: any) => { v.status = "approved"; }, (v: any) => { v.expired = true; },
    (v: any) => { v.decisions[1].original.previous_fingerprint = "0".repeat(64); },
    (v: any) => { v.decisions[1].original.created_at = "2026-10-08T13:00:00.000002Z"; },
    (v: any) => { v.decisions[0].original.source_checked_at = "2026-10-08T13:00:00.000004Z"; },
    (v: any) => { v.decisions[0].original.operation_fingerprint = "0".repeat(64); },
    (v: any) => { v.current_source = "verified"; },
  ]) {
    const value = copy(fixture.revoked); attack(value);
    for (const entry of value.decisions) await rehash(entry);
    assert.equal(await validBaseApprovalState(value, "own"), false);
  }
  const selected = copy(fixture.operation); selected.fingerprint = "0".repeat(64);
  assert.equal(await validBaseApprovalState(fixture.approved, "own", selected), false);
});

test("execution requires exact operation and approval, unchanged cancelled result and receipt clock", async () => {
  for (const attack of [
    (v: any) => { v.original.operation_id = "invented"; }, (v: any) => { v.original.approval_fingerprint = "0".repeat(64); },
    (v: any) => { v.original.after.employee_id = "invented"; }, (v: any) => { v.original.after.status = "scheduled"; },
    (v: any) => { v.original.actor_id = "invented"; }, (v: any) => { v.original.booking_event_fingerprint = "truncated"; },
    (v: any) => { v.original.before.captured_at = "2026-10-08T13:00:00.000002Z"; },
    (v: any) => { v.original.created_at = fixture.operation.original.valid_until; },
    (v: any) => { v.original.effect = "contact_sent"; },
  ]) {
    const value = copy(fixture.execution); attack(value); await rehash(value);
    assert.equal(await validBaseExecutionEnvelope(value, "own", fixture.approved as BaseApprovalState), false);
  }
});

test("write requests forbid identity and executable injection, incomplete predecessor and implicit dates", () => {
  const o = fixture.operation.original;
  const operation = { capability: o.capability, selection: o.selection, expected_state_fingerprint: o.expected_state_fingerprint,
    valid_until: o.valid_until, reason: o.reason, idempotency_key: o.idempotency_key };
  const a = fixture.approved.decisions[0].original;
  const approval = { operation_id: a.operation_id, operation_fingerprint: a.operation_fingerprint, previous_id: a.previous_id,
    previous_fingerprint: a.previous_fingerprint, decision: a.decision, reason: a.reason, idempotency_key: a.idempotency_key };
  const e = fixture.execution.original;
  const execution = { operation_id: e.operation_id, operation_fingerprint: e.operation_fingerprint, approval_id: e.approval_id,
    approval_fingerprint: e.approval_fingerprint, reason: e.reason, idempotency_key: e.idempotency_key };
  for (const [request, validate] of [[operation, validBaseOperationRequest], [approval, validBaseDecisionRequest], [execution, validBaseExecutionRequest]] as const) {
    assert.equal(validate(request), true);
    assert.equal(validate({ ...request, actor_id: "injected" }), false);
    assert.equal(validate({ ...request, sql: "SELECT *" }), false);
    assert.equal(validate({ ...request, reason: "\n" }), false);
  }
  assert.equal(validBaseOperationRequest({ ...operation, valid_until: "2026-10-08" }), false);
  assert.equal(validBaseDecisionRequest({ ...approval, previous_fingerprint: "0".repeat(64) }), false);
  assert.equal(validBaseDecisionRequest({ ...approval, decision: "execute" }), false);
});
