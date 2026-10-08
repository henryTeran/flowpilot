import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { revenueOriginalFingerprint } from "../src/revenue-scenario-utils";
import { validBookingClosures, validPriceReferences, validClosureEnvelope, validClosureAudit } from "../src/revenue-closure-utils";
const vector = JSON.parse(readFileSync(new URL("./fixtures/revenue-closure-14s.json", import.meta.url), "utf8"));
const period = { start: vector.closure_report.window.start, end: vector.closure_report.window.end };
test("pure Python closure/reference/original contracts preserve raw SHA and refuse contradictory claims", async () => {
  assert.equal(validBookingClosures(vector.closure_report, "own", period, 0), true);
  assert.equal(await validPriceReferences(vector.references, "own", "booking", 0), true);
  assert.equal(await validClosureEnvelope(vector.original, "own", "booking"), true);
  assert.equal(await revenueOriginalFingerprint(vector.original.original), vector.original.fingerprint);
  for (const mutate of [
    (r: any) => { r.no_show_count = 0; }, (r: any) => { r.causal_loss_proven = 0; }, (r: any) => { r.opportunities[0].estimated_value = "0"; },
    (r: any) => { r.opportunities[0].evidence.after.service_id = "other"; }, (r: any) => { r.opportunities[0].evidence.after.actual_start_time = r.window.start; },
    (r: any) => { r.opportunities[0].evidence.occurred_at = r.window.end; }, (r: any) => { r.opportunities[0].action_executed = true; },
  ]) { const bad = structuredClone(vector.closure_report); mutate(bad); assert.equal(validBookingClosures(bad, "own", period, 0), false); }
  for (const mutate of [
    (o: any) => { o.estimated_value.amount_minor = "999"; }, (o: any) => { o.reference_event.institute_id = "foreign"; },
    (o: any) => { o.reference_event.after.service_id = "other"; }, (o: any) => { o.request.expected_fingerprint = "0".repeat(64); },
    (o: any) => { o.retained = 1; }, (o: any) => { o.causal_loss_proven = true; }, (o: any) => { o.created_at = "2020-01-01T00:00:00Z"; },
  ]) { const bad = structuredClone(vector.original); mutate(bad.original); bad.fingerprint = await revenueOriginalFingerprint(bad.original); assert.equal(await validClosureEnvelope(bad, "own"), false); }
});
test("known zero remains valued, uncertain currency stays unavailable and paging verifies full selected originals", async () => {
  const zero = structuredClone(vector.original); zero.original.reference.terms.member_minor = "0"; zero.original.reference.fingerprint = await revenueOriginalFingerprint(zero.original.reference.terms);
  zero.original.request.expected_fingerprint = zero.original.reference.fingerprint; zero.original.estimated_value.amount_minor = "0"; zero.fingerprint = await revenueOriginalFingerprint(zero.original);
  assert.equal(await validClosureEnvelope(zero, "own"), true);
  const unknown = structuredClone(zero); Object.assign(unknown.original.reference.terms, { currency: null, currency_settings_at: null, currency_settings_actor_id: null, currency_unavailable_reason: "settings_absent" });
  unknown.original.reference.fingerprint = await revenueOriginalFingerprint(unknown.original.reference.terms); unknown.original.request.expected_fingerprint = unknown.original.reference.fingerprint;
  unknown.original.estimated_value = null; unknown.original.unavailable_reason = "unknown_currency"; unknown.fingerprint = await revenueOriginalFingerprint(unknown.original);
  assert.equal(await validClosureEnvelope(unknown, "own"), true);
  unknown.original.estimated_value = zero.original.estimated_value; unknown.fingerprint = await revenueOriginalFingerprint(unknown.original); assert.equal(await validClosureEnvelope(unknown, "own"), false);
  const originals = await Promise.all(Array.from({ length: 25 }, async (_, n) => { const e = structuredClone(vector.original); e.original.id = `value-${String(n).padStart(2, "0")}`; e.original.idempotency_key = `key-${n}`; e.fingerprint = await revenueOriginalFingerprint(e.original); return e; }));
  const audit = { institute_id: "own", captured_at: vector.references.captured_at, offset: 0, limit: 20, total: 25, originals: originals.slice(0, 20), full_original_cohort_verified: true, causal_loss_proven: false, action_executed: false };
  assert.equal(await validClosureAudit(audit, "own", 0), true); assert.equal(await validClosureAudit({ ...audit, offset: 20, originals: originals.slice(20) }, "own", 20), true);
  assert.equal(await validClosureAudit({ ...audit, full_original_cohort_verified: 1 }, "own", 0), false);
  const wrong = structuredClone(audit); wrong.originals[1].original.idempotency_key = wrong.originals[0].original.idempotency_key; wrong.originals[1].fingerprint = await revenueOriginalFingerprint(wrong.originals[1].original);
  assert.equal(await validClosureAudit(wrong, "own", 0), false);
});
