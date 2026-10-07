import test from "node:test";
import assert from "node:assert/strict";
import { validSegmentProfile, type SegmentProfile } from "../src/crm-segment-utils";

import { crmProfile as profile } from "./crm-fixture";
const valid = (v: unknown) => validSegmentProfile(v, "i", "customer_a");
test("current segment verifies policy, registration, scope and exact classification", () => {
  assert.equal(valid(profile()), true);
  for (const mutate of [(r: SegmentProfile) => { r.segment!.state = "VIP"; },
    (r: SegmentProfile) => { r.segment!.reason = "recent_activity"; },
    (r: SegmentProfile) => { r.segment!.policy = { ...r.segment!.policy, vip_gross_minor: "301" }; },
    (r: SegmentProfile) => { r.segment!.billing.window.captured_at = "2026-10-07T00:00:00.000001Z"; },
    (r: SegmentProfile) => { r.segment!.customer = { ...r.customer, created_at: "2026-10-06T23:59:59.999951Z" }; },
    (r: SegmentProfile) => { r.segment!.undated_paid_tickets = 1; }]) {
    const r = profile(); mutate(r); assert.equal(valid(r), false);
  }
  assert.equal(validSegmentProfile(profile(), "other", "customer_a"), false);
  assert.equal(validSegmentProfile(profile(), "i", "other"), false);
});
test("unavailable and unknown sources retain their exact reason without fallback", () => {
  for (const reason of ["policy_absent", "future_policy", "future_registration", "future_closings"] as const) {
    const r = profile(); r.segment = null; r.unavailable_reason = reason;
    if (reason === "policy_absent") r.policy_original = null;
    if (reason === "future_policy") r.policy_original!.created_at = "2026-10-07T00:00:00.000001Z";
    if (reason === "future_registration") r.customer.created_at = "2026-10-07T00:00:00.000001Z";
    if (reason === "future_closings") r.future_paid_tickets = 1;
    assert.equal(valid(r), true); r.unavailable_reason = null; assert.equal(valid(r), false);
  }
  const r = profile(); r.undated_paid_tickets = r.segment!.undated_paid_tickets = 1;
  r.segment!.state = null; r.segment!.reason = "undated_closings"; assert.equal(valid(r), true);
  r.segment!.state = "NEW"; assert.equal(valid(r), false);
});

test("all six states preserve count, gross and exact recency boundaries", () => {
  for (const [count, age, state, reason] of [[1, 1, "ACTIVE", "recent_activity"], [2, 1, "LOYAL", "loyal_count"],
    [3, 1, "VIP", "vip_count_and_gross"], [3, 1000, "AT_RISK", "risk_recency"],
    [3, 2000, "DORMANT", "dormant_recency"]] as const) {
    const r = profile(), b = r.segment!.billing, gross = String(count*101);
    b.closed_tickets = count; b.frequency_per_microsecond.numerator = String(count);
    b.last_recorded_closed_at = `2026-10-06T23:59:59.${String(1000000-age).padStart(6, "0")}Z`;
    b.recorded_recency_us = String(age);
    b.currencies = [{ currency: "CHF", closed_tickets: count, known_amount_tickets: count,
      missing_amount_tickets: 0, invalid_amount_tickets: 0, known_gross_minor: gross,
      recorded_average_basket_minor: { numerator: gross, denominator: String(count) } }];
    r.segment!.state = state; r.segment!.reason = reason; assert.equal(valid(r), true);
    r.segment!.reason = "recent_registration"; assert.equal(valid(r), false);
  }
  const overflow = profile(); overflow.captured_at = overflow.customer.created_at = "0001-01-01T00:00:00Z";
  overflow.policy_original!.created_at = overflow.captured_at; overflow.segment = null;
  overflow.unavailable_reason = "unrepresentable_horizon"; assert.equal(valid(overflow), true);
});
