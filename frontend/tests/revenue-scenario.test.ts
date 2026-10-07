import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { revenueOriginalFingerprint, validRevenueAssumptions, validRevenueScenarioEnvelope, validRevenueScenarioAudit } from "../src/revenue-scenario-utils";
const vector = JSON.parse(readFileSync(new URL("./fixtures/revenue-scenario-14o.json", import.meta.url), "utf8"));
test("audit verifies 20/5-page boundaries, original ordering and unique recovery keys", async () => {
  const originals = await Promise.all(Array.from({ length: 25 }, async (_, n) => {
    const copy = structuredClone(vector); copy.original.id = `scenario-${String(n).padStart(2, "0")}`;
    copy.original.idempotency_key = `key-${n}`; copy.fingerprint = await revenueOriginalFingerprint(copy.original); return copy;
  }));
  const audit = { institute_id: "own", captured_at: vector.original.created_at, offset: 0, limit: 20, total: 25,
    originals: originals.slice(0, 20), full_original_cohort_verified: true, complete_sales_history: false, action_executed: false };
  assert.equal(await validRevenueScenarioAudit(audit, "own", 0), true);
  assert.equal(await validRevenueScenarioAudit({ ...audit, offset: 20, originals: originals.slice(20) }, "own", 20), true);
  assert.equal(await validRevenueScenarioAudit({ ...audit, originals: [audit.originals[1], audit.originals[0], ...audit.originals.slice(2)] }, "own", 0), false);
  const duplicate = structuredClone(audit); duplicate.originals[1].original.idempotency_key = duplicate.originals[0].original.idempotency_key;
  duplicate.originals[1].fingerprint = await revenueOriginalFingerprint(duplicate.originals[1].original);
  assert.equal(await validRevenueScenarioAudit(duplicate, "own", 0), false);
  assert.equal(await validRevenueScenarioAudit({ ...audit, full_original_cohort_verified: 1 }, "own", 0), false);
});
test("Python full original SHA agrees with browser Unicode and datetime-preserving canonical JSON", async () => {
  assert.equal(await revenueOriginalFingerprint(vector.original), vector.fingerprint);
  assert.equal(await validRevenueScenarioEnvelope(vector, "own"), true);
  assert.equal(await validRevenueScenarioEnvelope(vector, "foreign"), false);
  const changed = structuredClone(vector); changed.original.created_at = changed.original.created_at.replace("Z", "+00:00");
  assert.equal(await validRevenueScenarioEnvelope(changed, "own"), false);
  changed.fingerprint = await revenueOriginalFingerprint(changed.original);
  assert.equal(await validRevenueScenarioEnvelope(changed, "own"), true);
});
test("recomputed fingerprints do not excuse inconsistent original scope, flags, capture or projection", async () => {
  for (const mutation of [
    (o: any) => { o.projected_gross_minor.numerator = "999"; },
    (o: any) => { o.projected_gross_minor.denominator = "0"; },
    (o: any) => { o.retained = 1; }, (o: any) => { o.validated_prediction = 0; },
    (o: any) => { o.action_executed = true; },
    (o: any) => { o.evidence.window.institute_id = "foreign"; },
    (o: any) => { o.created_at = o.assumptions.projected_end; },
    (o: any) => { o.assumptions.activity_fraction.numerator = "4"; },
    (o: any) => { o.assumptions.observed_end = o.assumptions.observed_start; },
    (o: any) => { o.reason = " "; }, (o: any) => { o.extra = true; },
  ]) {
    const changed = structuredClone(vector); mutation(changed.original); changed.fingerprint = await revenueOriginalFingerprint(changed.original);
    assert.equal(await validRevenueScenarioEnvelope(changed, "own"), false);
  }
});
test("known-zero conditional fractions remain distinct from unavailable evidence", async () => {
  const multiline = structuredClone(vector); multiline.original.reason = "Scénario 😀\n2026-10-07T12:00:00Z";
  multiline.fingerprint = await revenueOriginalFingerprint(multiline.original);
  assert.equal(await validRevenueScenarioEnvelope(multiline, "own"), true); // Backend Reason accepts literal multiline text.
  const zero = structuredClone(vector); zero.original.assumptions.activity_fraction.numerator = "0";
  zero.original.projected_gross_minor = { numerator: "0", denominator: "1" }; zero.fingerprint = await revenueOriginalFingerprint(zero.original);
  assert.equal(await validRevenueScenarioEnvelope(zero, "own"), true);
  const missing = structuredClone(vector); missing.original.evidence.institute_undated_paid_tickets = 1;
  missing.original.projected_gross_minor = null; missing.original.unavailable_reason = "undated_paid_tickets";
  missing.fingerprint = await revenueOriginalFingerprint(missing.original);
  assert.equal(await validRevenueScenarioEnvelope(missing, "own"), true);
  missing.original.projected_gross_minor = { numerator: "0", denominator: "1" }; missing.fingerprint = await revenueOriginalFingerprint(missing.original);
  assert.equal(await validRevenueScenarioEnvelope(missing, "own"), false);
  assert.equal(validRevenueAssumptions({ ...vector.original.assumptions, activity_fraction: { numerator: "1", denominator: "0" } }), false);
});
