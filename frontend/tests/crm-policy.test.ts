import test from "node:test";
import assert from "node:assert/strict";
import { validPolicyOriginal, validPolicyTerms, validSegmentPolicy, matchesPolicyReceipt, samePolicyOriginal,
  type PolicyOriginal } from "../src/crm-policy-utils";

function original(): PolicyOriginal {
  return { id: "policy_a", institute_id: "i", actor_id: "manager", created_at: "2026-10-07T00:00:00.000001Z",
    reason: "Explicit configuration", idempotency_key: "key", previous_policy_id: null,
    policy: { institute_id: "i", observation_us: 86400000000, new_customer_us: 100,
      at_risk_us: 1000, dormant_us: 2000, loyal_min_tickets: 2, vip_min_tickets: 3,
      vip_currency: "CHF", vip_gross_minor: "300" } };
}
test("policy guards verify scope, explicit thresholds and original identity", () => {
  const r = original(); assert.equal(validPolicyOriginal(r, "i"), true);
  assert.equal(validPolicyTerms({ policy: r.policy, previous_policy_id: null, reason: r.reason, idempotency_key: r.idempotency_key }, "i"), true);
  for (const changes of [{ at_risk_us: 2000 }, { dormant_us: 86400000000 }, { new_customer_us: 86400000001 },
    { vip_min_tickets: 2 }, { vip_min_tickets: true }, { observation_us: Number.MAX_SAFE_INTEGER+1 },
    { observation_us: "86400000000" }, { vip_currency: "USD" }, { vip_gross_minor: "01" }, { institute_id: "foreign" }]) {
    assert.equal(validSegmentPolicy({ ...r.policy, ...changes }, "i"), false);
  }
  for (const changes of [{ previous_policy_id: undefined }, { previous_policy_id: r.id },
    { actor_id: "" }, { reason: "  " }, { created_at: "2026-10-07" }, { institute_id: "foreign" }]) {
    assert.equal(validPolicyOriginal({ ...r, ...changes }, "i"), false);
  }
  assert.equal(validPolicyOriginal(null, "i"), false);
});
test("receipt comparison pins actor, predecessor, terms, key and exact semantic instant", () => {
  const r = original(); assert.equal(matchesPolicyReceipt(r, r, "manager"), true);
  assert.equal(matchesPolicyReceipt(r, r, "other"), false);
  assert.equal(samePolicyOriginal(r, { ...r, created_at: "2026-10-07T02:00:00.000001+02:00" }), true);
  for (const changes of [{ id: "other" }, { previous_policy_id: "prior" }, { actor_id: "other" },
    { idempotency_key: "other" }, { reason: "Another reason" }, { created_at: "2026-10-07T00:00:00.000002Z" },
    { policy: { ...r.policy, vip_gross_minor: "301" } }]) {
    assert.equal(samePolicyOriginal(r, { ...r, ...changes }), false);
  }
});
