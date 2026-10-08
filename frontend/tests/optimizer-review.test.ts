import test from "node:test";
import assert from "node:assert/strict";
import fixture from "./fixtures/optimizer-review-16g.json";
import { validOptimizerReview, type OptimizerReview, type OptimizerReviewSelection } from "../src/optimizer-review-utils";
import { revenueOriginalFingerprint } from "../src/revenue-scenario-utils";
const selection = (v: any): OptimizerReviewSelection => ({ state: v.source.state, horizon_end: v.source.horizon_end,
  policy: v.source.policy, policyOriginal: v.policy_original });
const base = fixture.options as OptimizerReview;
test("actual typed adapter/kernel vectors verify complete scores, exact delay saturation, unknown factors and source refusals", async () => {
  for (const [name, value] of Object.entries(fixture)) assert.equal(await validOptimizerReview(value, "own", selection(value)), true, name);
  assert.equal(await validOptimizerReview(base, "foreign", selection(base)), false);
});
test("selected original/full SHA, matching version/horizon/policy and shared clocks are mandatory", async () => {
  for (const change of [(s: any) => s.policyOriginal.fingerprint = "0".repeat(64), (s: any) => s.horizon_end = "2026-10-09T12:00:00Z",
    (s: any) => s.policy.permission_requirement = "recorded_grant_required", (s: any) => s.state.events.at(-1).fingerprint = "0".repeat(64)]) {
    const s = structuredClone(selection(base)); change(s); assert.equal(await validOptimizerReview(base, "own", s), false);
  }
  for (const change of [(v: any) => v.captured_at = "2026-10-08T10:00:00Z", (v: any) => v.review.policy.id = "other",
    (v: any) => v.review.policy.weights[1].value.numerator = "2", (v: any) => v.policy_original.original.reason = "Other reason",
    (v: any) => v.review.source.capture.customer_capacity = "unknown"]) {
    const v = structuredClone(base); change(v); assert.equal(await validOptimizerReview(v, "own", selection(base)), false);
  }
});
test("every raw proof is source-bound; no guessed money/preferences, changed denominator, clock or quantity", async () => {
  const changes = [(v: any) => v.proofs[0].containing_employee_window.end = "2026-10-08T23:00:00Z",
    (v: any) => v.proofs[0].factors[1].source.denominator = "1", (v: any) => v.proofs[0].factors[1].source.quantity = "1",
    (v: any) => v.proofs[0].factors[1].source.reference = "invented", (v: any) => v.proofs[0].factors[1].source.observed_at = "2030-01-01T00:00:00Z",
    (v: any) => v.proofs[0].factors[0].source.quantity = "0", (v: any) => v.proofs[0].factors[3].observation.value = { numerator: "0", denominator: "1" },
    (v: any) => v.proofs[0].factors[7].source.quantity = "1", (v: any) => v.proofs[0].factors.pop(), (v: any) => v.proofs.push(v.proofs[0])];
  for (const change of changes) { const v = structuredClone(base); change(v); assert.equal(await validOptimizerReview(v, "own", selection(base)), false); }
});
test("contribution/score/reason/constraints/rank and complete source coverage cannot disagree", async () => {
  for (const change of [(v: any) => v.review.options[0].score.numerator = "999", (v: any) => v.review.options[0].rank = 0,
    (v: any) => v.review.options[0].contributions[1].direction = "penalty", (v: any) => v.review.options[0].contributions[1].contribution.numerator = "999",
    (v: any) => v.review.options[0].reasons[0] = "A made-up recommendation", (v: any) => v.review.options[0].constraints[0].state = "unknown",
    (v: any) => v.review.options[0].constraints[0].reference = "invented", (v: any) => v.review.options[0].constraints.pop(),
    (v: any) => v.review.options.pop(), (v: any) => v.review.options[0].option.employee_id = "foreign", (v: any) => v.review.ranking = "incomplete_evidence",
    (v: any) => v.action = "book_now", (v: any) => v.extra = true]) {
    const v = structuredClone(base); change(v); assert.equal(await validOptimizerReview(v, "own", selection(base)), false);
  }
});
test("unknown weighted evidence cannot acquire a zero, rank, partial best or score", async () => {
  const original = fixture.revenue_score;
  for (const change of [(v: any) => v.review.options[0].rank = 1, (v: any) => v.review.options[0].score = { numerator: "0", denominator: "1" },
    (v: any) => v.review.ranking = "complete", (v: any) => v.review.options[0].contributions[0].state = "included"]) {
    const v = structuredClone(original); change(v); assert.equal(await validOptimizerReview(v, "own", selection(original)), false);
  }
});
test("source refusal carries no scoring proofs or catalog; policy rehash cannot evade selected original binding", async () => {
  const original = fixture.permission_refused;
  for (const change of [(v: any) => v.review = base.review, (v: any) => v.proofs = base.proofs, (v: any) => v.catalog = base.catalog]) {
    const v = structuredClone(original); change(v); assert.equal(await validOptimizerReview(v, "own", selection(original)), false);
  }
  const v = structuredClone(base); v.policy_original.original.reason = "Rehashed alternative policy";
  v.policy_original.fingerprint = await revenueOriginalFingerprint(v.policy_original.original);
  assert.equal(await validOptimizerReview(v, "own", selection(base)), false);
});
test("multiple options must follow exact descending scores and source identity ties with competition ranks", async () => {
  assert.equal(fixture.multiple.proofs.length, 2);
  assert.deepEqual(fixture.multiple.review!.options.map(r => r.rank), [1, 2]);
  assert.deepEqual(fixture.multiple_tie.review!.options.map(r => r.rank), [1, 1]);
  for (const name of ["multiple", "multiple_tie"] as const) {
    const original = fixture[name];
    for (const change of [(v: any) => v.proofs.reverse(), (v: any) => v.review.options.reverse(),
      (v: any) => v.review.options[1].rank = 3, (v: any) => v.review.options[1] = v.review.options[0]]) {
      const v = structuredClone(original); change(v); assert.equal(await validOptimizerReview(v, "own", selection(original)), false);
    }
  }
});
