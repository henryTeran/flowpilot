import test from "node:test";
import assert from "node:assert/strict";
import { validSegmentProfile, type SegmentProfile } from "../src/crm-segment-utils";

function profile(): SegmentProfile {
  const customer = { institute_id: "i", customer_id: "customer_a", created_at: "2026-10-06T23:59:59.999950Z" };
  const policy = { institute_id: "i", observation_us: 86400000000, new_customer_us: 100,
    at_risk_us: 1000, dormant_us: 2000, loyal_min_tickets: 2, vip_min_tickets: 3, vip_currency: "CHF" as const, vip_gross_minor: "300" };
  return { institute_id: "i", customer_id: "customer_a", captured_at: "2026-10-07T00:00:00Z", customer,
    policy_original: { id: "p", institute_id: "i", actor_id: "manager", created_at: "2026-10-06T00:00:00Z", policy,
      reason: "Explicit policy", idempotency_key: "key", previous_policy_id: null },
    undated_paid_tickets: 0, future_paid_tickets: 0, unavailable_reason: null, complete_customer_history: false,
    segment: { basis: "declared_policy_observed_billing", policy, customer, undated_paid_tickets: 0,
      state: "NEW", reason: "recent_registration", complete_customer_history: false,
      billing: { window: { institute_id: "i", customer_id: "customer_a", start: "2026-10-06T00:00:00Z",
        end: "2026-10-07T00:00:00Z", captured_at: "2026-10-07T00:00:00Z" }, basis: "retained_closed_tickets",
        closed_tickets: 0, frequency_per_microsecond: { numerator: "0", denominator: "86400000000" },
        last_recorded_closed_at: null, recorded_recency_us: null, unknown_currency_tickets: 0, currencies: [],
        complete_customer_history: false, complete_currency_classification: true, predicted_clv: null } } };
}
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
