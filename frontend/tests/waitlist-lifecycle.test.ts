import test from "node:test";
import assert from "node:assert/strict";
import fixture from "./fixtures/waitlist-lifecycle-15j.json";
import { validWaitlistLifecycleAudit, validWaitlistLifecycleEnvelope, validWaitlistLifecycleState, validWaitlistLifecycleRequest, type WaitlistLifecycleState } from "../src/waitlist-lifecycle-utils";
import { revenueOriginalFingerprint } from "../src/revenue-scenario-utils";
async function rehash(state: WaitlistLifecycleState) {
  for (let n = 0; n < state.events.length; n++) {
    if (n) state.events[n].original.previous_fingerprint = state.events[n-1].fingerprint;
    state.events[n].fingerprint = await revenueOriginalFingerprint(state.events[n].original);
  }
}
test("backend typed full lifecycle proofs preserve revisions, equal causal clocks and expired administrative state", async () => {
  for (const state of [fixture.activated, fixture.revised, fixture.cancelled]) assert.equal(await validWaitlistLifecycleState(state, "own"), true);
  assert.equal(await validWaitlistLifecycleAudit(fixture.audit, "own", 0), true);
  assert.equal(await validWaitlistLifecycleAudit(fixture.audit, "other", 0), false);
  const { id, institute_id, actor_id, created_at, activation_source, effect, ...request } = fixture.activated.events[0].original;
  assert.equal(validWaitlistLifecycleRequest(request), true);
  assert.equal(validWaitlistLifecycleRequest({ ...request, previous_id: "unexpected" }), false);
  assert.equal(validWaitlistLifecycleRequest({ ...request, action: "cancel" }), false);
  assert.equal(validWaitlistLifecycleRequest({ ...request, extra: true }), false);
  const expired = structuredClone(fixture.audit); expired.captured_at = "2035-01-01T00:00:00Z";
  assert.equal(await validWaitlistLifecycleAudit(expired, "own", 0), true);
});
test("rehashing cannot repair contradictions in returned demand/source and causal transition claims", async () => {
  for (const mutate of [
    (s: WaitlistLifecycleState) => { s.events[1].original.activation_source!.duration_minutes = 31; },
    (s: WaitlistLifecycleState) => { s.events[1].original.activation_source!.customer_id = "foreign"; },
    (s: WaitlistLifecycleState) => { s.events[1].original.activation_source!.registered_at = "2026-10-08T10:04:00Z"; },
    (s: WaitlistLifecycleState) => { s.events[2].original.target_id = s.root.original.id; s.events[2].original.target_fingerprint = s.root.fingerprint; },
    (s: WaitlistLifecycleState) => { s.events[1].original.target_id = s.root.original.id; s.events[1].original.target_fingerprint = s.root.fingerprint; },
    (s: WaitlistLifecycleState) => { s.events[2].original.activation_source = s.events[1].original.activation_source; },
    (s: WaitlistLifecycleState) => { s.events[1].original.root_fingerprint = "a".repeat(64); },
    (s: WaitlistLifecycleState) => { s.events[1].original.previous_id = "unrelated"; },
    (s: WaitlistLifecycleState) => { s.events[1].original.idempotency_key = s.events[0].original.idempotency_key; },
    (s: WaitlistLifecycleState) => { s.events[1].original.created_at = "2026-10-08T10:00:30Z"; },
    (s: WaitlistLifecycleState) => { s.events[1].original.effect = "booking_created" as any; },
  ]) {
    const state = structuredClone(fixture.cancelled) as WaitlistLifecycleState; mutate(state); await rehash(state);
    assert.equal(await validWaitlistLifecycleState(state, "own"), false);
  }
});
test("full raw SHA, predecessor fingerprints, terminal state and event order refuse substitution", async () => {
  const corrupt = structuredClone(fixture.cancelled); corrupt.events[0].original.reason = "Changed reason";
  assert.equal(await validWaitlistLifecycleEnvelope(corrupt.events[0], "own"), false);
  const stale = structuredClone(fixture.cancelled); stale.events[1].original.previous_fingerprint = "f".repeat(64);
  stale.events[1].fingerprint = await revenueOriginalFingerprint(stale.events[1].original);
  assert.equal(await validWaitlistLifecycleState(stale, "own"), false);
  const order = structuredClone(fixture.cancelled); order.events.reverse(); assert.equal(await validWaitlistLifecycleState(order, "own"), false);
  const terminal = structuredClone(fixture.cancelled); terminal.state = "active"; assert.equal(await validWaitlistLifecycleState(terminal, "own"), false);
  const after = structuredClone(fixture.cancelled); after.events.push(structuredClone(fixture.revised.events[1]));
  assert.equal(await validWaitlistLifecycleState(after, "own"), false);
  assert.equal(await validWaitlistLifecycleState({ ...fixture.revised, current_demand: fixture.activated.root }, "own"), false);
});
test("audit enforces partitions, exact page cardinality, root order, capture chronology and cross-root uniqueness", async () => {
  for (const audit of [
    { ...fixture.audit, active: 2 }, { ...fixture.audit, active: 2, cancelled: 0 }, { ...fixture.audit, total: 3, active: 2 },
    { ...fixture.audit, offset: 20 }, { ...fixture.audit, limit: 50 }, { ...fixture.audit, captured_at: "2026-10-08T10:02:00Z" },
    { ...fixture.audit, states: [...fixture.audit.states].reverse() }, { ...fixture.audit, states: [fixture.audit.states[0], fixture.audit.states[0]] },
  ]) assert.equal(await validWaitlistLifecycleAudit(audit, "own", 0), false);
  const partial = { ...fixture.audit, total: 21, active: 20, cancelled: 1, offset: 20, states: [fixture.audit.states[1]] };
  assert.equal(await validWaitlistLifecycleAudit(partial, "own", 20), true);
  assert.equal(await validWaitlistLifecycleAudit({ ...partial, states: [] }, "own", 20), false);
});
