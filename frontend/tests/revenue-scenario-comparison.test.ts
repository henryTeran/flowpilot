import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { revenueOriginalFingerprint, validRevenueScenarioComparison, validRevenueScenarioSelection } from "../src/revenue-scenario-utils";
const vector = JSON.parse(readFileSync(new URL("./fixtures/revenue-scenario-14o.json", import.meta.url), "utf8"));
export async function comparisonFixture() {
  const zero = structuredClone(vector); zero.original.id = "zero"; zero.original.idempotency_key = "zero-key";
  zero.original.assumptions.activity_fraction.numerator = "0"; zero.original.projected_gross_minor = { numerator: "0", denominator: "1" }; zero.fingerprint = await revenueOriginalFingerprint(zero.original);
  const selection = { baseline: { original_id: vector.original.id, fingerprint: vector.fingerprint }, alternatives: [{ original_id: zero.original.id, fingerprint: zero.fingerprint }] };
  const frame: any = { institute_id: "own", captured_at: vector.original.created_at, baseline_original_id: vector.original.id, selected_count: 2,
    variants: [vector, zero].map((e, i) => ({ original: e, is_baseline: i === 0, same_source_capture: true, same_recorded_billing_aggregates: true,
      difference_from_baseline_minor: { numerator: i ? "-101" : "0", denominator: i ? "2" : "1" }, difference_unavailable_reason: null, difference_basis: "comparison_only_not_attributed_effect" })),
    currencies: [{ currency: "CHF", selected_count: 2, valued_count: 2, unavailable_count: 0, summed_projected_gross_minor: null }],
    basis: "explicit_retained_scenario_comparison", confidence: "conditional_unvalidated_scenarios", summed_projected_gross_minor: null,
    validated_prediction: false, causal_effect_confirmed: false, action_executed: false, full_institute_scenario_cohort: false };
  return { selection, frame };
}
test("comparison binds explicit ordered originals, exact negative/zero deltas and separated counts", async () => {
  const { selection, frame } = await comparisonFixture(); assert.equal(await validRevenueScenarioComparison(frame, "own", selection), true);
  for (const change of [
    (f: any) => { f.variants.reverse(); }, (f: any) => { f.variants[1].difference_from_baseline_minor.numerator = "-100"; },
    (f: any) => { f.variants[0].difference_from_baseline_minor.denominator = "2"; }, (f: any) => { f.variants[1].is_baseline = true; },
    (f: any) => { f.variants[1].same_source_capture = 1; }, (f: any) => { f.variants[1].same_recorded_billing_aggregates = false; },
    (f: any) => { f.currencies[0].valued_count = 1; }, (f: any) => { f.currencies[0].summed_projected_gross_minor = "101"; },
    (f: any) => { f.full_institute_scenario_cohort = true; }, (f: any) => { f.causal_effect_confirmed = 0; },
    (f: any) => { f.captured_at = "2020-01-01T00:00:00Z"; }, (f: any) => { f.selected_count = 3; },
  ]) { const bad = structuredClone(frame); change(bad); assert.equal(await validRevenueScenarioComparison(bad, "own", selection), false); }
  assert.equal(await validRevenueScenarioComparison(frame, "foreign", selection), false);
  assert.equal(validRevenueScenarioSelection({ ...selection, alternatives: [selection.baseline] }), false);
  assert.equal(validRevenueScenarioSelection({ ...selection, alternatives: [] }), false);
  assert.equal(validRevenueScenarioSelection({ ...selection, alternatives: Array(20).fill(selection.alternatives[0]) }), false);
});
test("unavailable comparisons never invent zero and aggregate equality ignores clock spelling only", async () => {
  const { selection, frame } = await comparisonFixture(), v = frame.variants[1], o = v.original.original;
  o.assumptions.currency = "EUR"; o.projected_gross_minor = null; o.unavailable_reason = "no_selected_currency";
  v.original.fingerprint = await revenueOriginalFingerprint(o); selection.alternatives[0].fingerprint = v.original.fingerprint;
  v.difference_from_baseline_minor = null; v.difference_unavailable_reason = "currency_difference";
  frame.currencies = [{ ...frame.currencies[0], selected_count: 1, valued_count: 1 }, { currency: "EUR", selected_count: 1, valued_count: 0, unavailable_count: 1, summed_projected_gross_minor: null }];
  assert.equal(await validRevenueScenarioComparison(frame, "own", selection), true);
  v.difference_from_baseline_minor = { numerator: "0", denominator: "1" }; assert.equal(await validRevenueScenarioComparison(frame, "own", selection), false); v.difference_from_baseline_minor = null;
  o.created_at = "2026-01-03T12:00:00+00:00"; o.evidence.window.captured_at = o.created_at; v.same_source_capture = false; frame.captured_at = o.created_at;
  o.evidence.window.start = o.evidence.window.start.replace("Z", "+00:00"); v.original.fingerprint = await revenueOriginalFingerprint(o); selection.alternatives[0].fingerprint = v.original.fingerprint;
  assert.equal(await validRevenueScenarioComparison(frame, "own", selection), true);
  v.same_recorded_billing_aggregates = false; assert.equal(await validRevenueScenarioComparison(frame, "own", selection), false);
});
