import test from "node:test";
import assert from "node:assert/strict";
import fixture from "./fixtures/waitlist-matching-15l.json";
import { validWaitlistMatching, validWaitlistPolicy, validWaitlistDetection, type WaitlistMatching, type WaitlistMatchingSelection } from "../src/waitlist-matching-utils";
const selection = (r: WaitlistMatching): WaitlistMatchingSelection => ({ state: r.state, horizon_end: r.horizon_end, policy: r.policy });
const base = fixture.options as WaitlistMatching;
test("typed backend matching preserves conditional options, source refusals, observed grants and queue partitions", async () => {
  for (const [name, value] of Object.entries(fixture)) {
    if (name.startsWith("detection")) continue;
    const r = value as WaitlistMatching;
    assert.equal(await validWaitlistMatching(r, "own", selection(r)), true, name);
  }
  assert.equal(await validWaitlistMatching(base, "foreign", selection(base)), false);
  assert.equal(validWaitlistPolicy({ ...base.policy, extra: true }), false);
  assert.equal(validWaitlistPolicy({ ...base.policy, channel: "phone" }), false);
});
test("typed whole-cohort detection verifies twenty-row paging and counts conditional alternatives rather than reservations", async () => {
  for (const page of [fixture.detection, fixture.detection_0, fixture.detection_20, fixture.detection_40]) {
    assert.equal(await validWaitlistDetection(page, "own", page.horizon_end, page.policy as WaitlistMatching["policy"], page.offset), true);
  }
  for (const mutate of [
    (r: any) => { r.active++; },
    (r: any) => { r.with_options++; },
    (r: any) => { r.unavailable_reasons.queue_projection_unknown = 0; },
    (r: any) => { r.unavailable_reasons = { invented: 1 }; },
    (r: any) => { r.reviews.pop(); },
    (r: any) => { r.reviews[1] = structuredClone(r.reviews[0]); },
    (r: any) => { r.reviews.reverse(); },
    (r: any) => { r.reviews[0].captured_at = "2026-10-08T10:06:00Z"; },
    (r: any) => { r.reviews[0].state = fixture.cancelled.state; },
    (r: any) => { r.limit = 50; },
    (r: any) => { r.allocation = "jointly_reserved"; },
  ]) {
    const page = structuredClone(fixture.detection_0); mutate(page);
    assert.equal(await validWaitlistDetection(page, "own", page.horizon_end, page.policy as WaitlistMatching["policy"], 0), false);
  }
  assert.equal(await validWaitlistDetection(fixture.detection_20, "own", base.horizon_end, base.policy, 0), false);
  const page = structuredClone(fixture.detection);
  page.with_options = 0; page.without_options = 1; page.unavailable_reasons = { no_matching_recorded_capacity: 1 };
  assert.equal(await validWaitlistDetection(page, "own", base.horizon_end, base.policy, 0), false);
});
test("current matching must bind the exact selected causal version, explicit policy and horizon", async () => {
  for (const mutate of [
    (r: any) => { r.horizon_end = "2026-10-08T15:00:00Z"; },
    (r: any) => { r.policy.channel = "sms"; },
    (r: any) => { r.state = fixture.cancelled.state; },
    (r: any) => { r.captured_at = "2026-10-08T10:02:00Z"; },
    (r: any) => { r.state.current_demand.original.reason = "Unverified replacement"; },
    (r: any) => { r.action = "book_now"; },
    (r: any) => { r.evidence.opening_hours = "verified"; },
  ]) {
    const r = structuredClone(base); mutate(r);
    assert.equal(await validWaitlistMatching(r, "own", selection(base)), false);
  }
  const equivalent = structuredClone(base); equivalent.horizon_end = "2026-10-08T15:05:00+02:00";
  assert.equal(await validWaitlistMatching(equivalent, "own", selection(base)), true);
});
test("displayed options require complete distinct resource units, skill and customer/employee interval fit", async () => {
  assert.equal(base.review!.options[0].resource_ids.length, 2);
  for (const mutate of [
    (r: any) => { r.review.options[0].resource_ids = ["room-flex", "room-flex"]; },
    (r: any) => { r.review.options[0].resource_ids = ["room-clean"]; },
    (r: any) => { r.review.capture.resources[0].capabilities = ["clean"]; },
    (r: any) => { r.review.capture.resources[0].state = "unknown"; },
    (r: any) => { r.review.capture.employees[0].skills = []; },
    (r: any) => { r.review.capture.employees[0].windows = []; },
    (r: any) => { r.review.options[0].end = "2026-10-08T11:31:00Z"; },
    (r: any) => { r.review.capture.customer_blockers = [{ start: "2026-10-08T11:20:00Z", end: "2026-10-08T11:40:00Z" }]; },
    (r: any) => { r.review.capture.resources[0].reservations = [{ start: "2026-10-08T11:20:00Z", end: "2026-10-08T11:40:00Z" }]; },
    (r: any) => { r.review.options.push(structuredClone(r.review.options[0])); },
    (r: any) => { r.review.capture.service.duration_minutes = 45; },
    (r: any) => { r.review.demand.allowed_employee_ids = []; },
  ]) {
    const r = structuredClone(base); mutate(r);
    assert.equal(await validWaitlistMatching(r, "own", selection(base)), false);
  }
});
test("policy refusal cannot fabricate a reason or promote absent/future/refused consent into a grant", async () => {
  for (const mutate of [
    (r: any) => { r.evidence.permission_original.declaration.communications[0].permission = "refused"; },
    (r: any) => { r.evidence.permission_original.customer_id = "other"; },
    (r: any) => { r.evidence.permission_original.created_at = "2026-10-08T14:00:00Z"; r.evidence.permission_reason = "future_declaration"; },
    (r: any) => { r.review.capture.customer.history_reference = "unrelated-ticket"; },
    (r: any) => { r.evidence.latest_care.completed_at = "2026-10-08T14:00:00Z"; },
    (r: any) => { r.evidence.care_diagnostics.unlinked_ticket = 1; },
    (r: any) => { r.evidence.permission_original = null; r.evidence.permission_reason = "declaration_absent"; },
  ]) {
    const r = structuredClone(fixture.observed_granted) as WaitlistMatching; mutate(r);
    assert.equal(await validWaitlistMatching(r, "own", selection(r)), false);
  }
  const denied = structuredClone(fixture.history_refused) as WaitlistMatching;
  denied.unavailable_reason = "permission_requirement_unmet";
  assert.equal(await validWaitlistMatching(denied, "own", selection(denied)), false);
  const forged = structuredClone(fixture.permission_refused) as WaitlistMatching;
  forged.policy.permission_requirement = "review_only";
  assert.equal(await validWaitlistMatching(forged, "own", selection(forged)), false);
});
test("known queue evidence binds employee/resource blockers and unknown tickets cannot become free capacity", async () => {
  for (const mutate of [
    (r: any) => { r.evidence.waiting_tickets = 2; },
    (r: any) => { r.evidence.queue_slots[0].employee_id = "foreign-employee"; },
    (r: any) => { r.evidence.queue_slots[0].resource_ids = ["foreign-resource"]; },
    (r: any) => { r.review.capture.resources[1].reservations = []; },
    (r: any) => { r.review.capture.employees[0].windows[0].start = r.captured_at; },
    (r: any) => { r.evidence.employee_reasons = {}; },
  ]) {
    const r = structuredClone(fixture.queue_known) as WaitlistMatching; mutate(r);
    assert.equal(await validWaitlistMatching(r, "own", selection(r)), false);
  }
  const r = structuredClone(fixture.queue_unknown) as WaitlistMatching;
  r.review!.capture.queue_capacity = "known";
  assert.equal(await validWaitlistMatching(r, "own", selection(r)), false);
});
test("malformed nested source or an extra contract field refuses without throwing", async () => {
  for (const mutate of [
    (r: any) => { r.evidence.queue_slots = [null]; },
    (r: any) => { r.review.capture.employees = [null]; },
    (r: any) => { r.review.options = [null]; },
    (r: any) => { r.evidence.observed_care_episodes = Number.MAX_SAFE_INTEGER + 1; },
    (r: any) => { r.review.capture.customer.extra = true; },
    (r: any) => { r.extra = true; },
    (r: any) => { r.review.unavailable_reason = "unknown_custom_rule"; },
  ]) {
    const r = structuredClone(base); mutate(r);
    assert.equal(await validWaitlistMatching(r, "own", selection(base)), false);
  }
});
