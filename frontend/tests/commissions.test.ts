import test from "node:test";
import assert from "node:assert/strict";
import { validCommission, validCommissionRule, validCommissionDay, validCommissionPage, sameCommissionOriginal,
  sameCommissionRuleOriginal, validCommissionRuleTerms, validCommissionIntent, commissionMinor, commissionStates } from "../src/commission-utils";
import { rule, original, snapshot, props } from "./commission-fixture";
const day = (v: unknown, offset = 0) => validCommissionDay(v, props.institute, props.employee, props.day, props.start, props.end, props.timezone, offset);
test("original commission verifies pinned scopes, exact gross-line arithmetic and cancellation chronology", () => {
  assert.equal(validCommission(original(), "inst", "emp"), true); assert.equal(validCommissionRule(rule(), "inst", "emp"), true);
  for (const mutate of [
    (r: ReturnType<typeof original>) => { r.calculation.amount_minor = "103"; },
    (r: ReturnType<typeof original>) => { r.calculation.amount_minor = "312"; },
    (r: ReturnType<typeof original>) => { r.calculation.unrounded_numerator = "1035001"; },
    (r: ReturnType<typeof original>) => { r.calculation.rounding_remainder = 4999; },
    (r: ReturnType<typeof original>) => { r.calculation.source.employee_id = "cashier"; },
    (r: ReturnType<typeof original>) => { r.calculation.source.currency = "EUR"; },
    (r: ReturnType<typeof original>) => { r.calculation.terms.rate_basis_points = 2000; },
    (r: ReturnType<typeof original>) => { r.calculation.source.paid_at = props.end; },
    (r: ReturnType<typeof original>) => { r.calculation.source.captured_at = "2026-10-25T12:00:00.000002Z"; },
    (r: ReturnType<typeof original>) => { r.calculation.source.gross_minor = "01035"; },
  ]) { const r = original(); mutate(r); assert.equal(validCommission(r, "inst", "emp"), false); }
  for (const [rounding, gross, amount] of [["half_up", "1025", "103"], ["half_even", "1025", "102"], ["down", "1035", "103"]] as const) {
    const r = original(); r.rule_capture.rounding = r.calculation.terms.rounding = rounding; r.calculation.source.gross_minor = gross;
    r.calculation.unrounded_numerator = String(BigInt(gross)*1000n); r.calculation.amount_minor = amount;
    assert.equal(validCommission(r, "inst", "emp"), true);
  }
  for (const rate of [0, 10000]) {
    const r = original(); r.rule_capture.rate_basis_points = r.calculation.terms.rate_basis_points = rate;
    r.calculation.source.gross_minor = "9999999999"; r.calculation.unrounded_numerator = String(9999999999n*BigInt(rate));
    r.calculation.rounding_remainder = 0; r.calculation.amount_minor = rate === 0 ? "0" : "9999999999";
    assert.equal(validCommission(r, "inst"), true);
  }
  const cancelled = original(); cancelled.cancellation = { id: "cancel", institute_id: "inst", commission_id: cancelled.id,
    actor_id: "another-manager", reason: "Correction", idempotency_key: "cancel-key", created_at: "2026-10-25T12:00:00.000002Z" };
  assert.equal(validCommission(cancelled, "inst"), true); assert.equal(sameCommissionOriginal(original(), cancelled), true);
  cancelled.cancellation.created_at = "2026-10-25T12:00:00Z"; assert.equal(validCommission(cancelled, "inst"), false);
  const alias = original(); alias.calculation.source.paid_at = "2026-10-25T13:00:00+02:00";
  assert.equal(sameCommissionOriginal(original(), alias), true); alias.calculation.source.paid_at = "2026-10-25T11:00:00.000001Z";
  assert.equal(sameCommissionOriginal(original(), alias), false);
});
test("rule terms are explicit and retain original calendar, zero/max rates and recovery captures", () => {
  for (const value of [true, "1000", 0.5, -1, 10001]) assert.equal(validCommissionRuleTerms({ ...rule(), rate_basis_points: value }), false);
  for (const value of [0, 10000]) assert.equal(validCommissionRuleTerms({ ...rule(), rate_basis_points: value }), true);
  assert.equal(validCommissionRuleTerms({ ...rule(), service_id: undefined }), false);
  assert.equal(validCommissionRule({ ...rule(), period_end: "2026-10-25T22:00:00Z" }, "inst"), false);
  assert.equal(validCommissionRule({ ...rule(), timezone: "bad-zone" }, "inst"), false);
  const r = rule(); r.rate_basis_points = 2000; assert.equal(sameCommissionRuleOriginal(rule(), r), false);
  assert.equal(validCommissionIntent({ type: "cancel", original: original(), terms: { reason: "Correction", idempotency_key: "correction" } }, "inst"), true);
  assert.equal(commissionMinor("9007199254740993"), 9007199254740993n);
  for (const v of [1, true, "1.0", "1e2", "01", "-1"]) assert.equal(commissionMinor(v), undefined);
});
test("recorded day independently checks states, complete and partial currency totals and active source uniqueness", () => {
  assert.equal(day(snapshot()), true);
  for (const mutate of [
    (r: ReturnType<typeof snapshot>) => { r.currencies[0].amounts_minor.recorded = "105"; },
    (r: ReturnType<typeof snapshot>) => { r.counts.cancelled = 1; },
    (r: ReturnType<typeof snapshot>) => { r.currencies[0].currency = "EUR"; },
    (r: ReturnType<typeof snapshot>) => { r.rows[0].state = "cancelled"; },
    (r: ReturnType<typeof snapshot>) => { r.rows[0].original.created_at = props.end; },
  ]) { const r = snapshot(); mutate(r); assert.equal(day(r), false); }
  assert.equal(day({ ...snapshot(), complete_entitlement: true }), false); assert.equal(day({ ...snapshot(), payable_total: "1.04" }), false);
  const future = snapshot(); future.generated_at = "2026-10-25T12:00:00Z"; future.rows[0].state = "future_recording";
  future.counts.recorded = 0; future.counts.future_recording = 1; future.currencies[0].counts = { ...future.counts };
  future.currencies[0].amounts_minor.recorded = "0"; future.currencies[0].amounts_minor.future_recording = "104";
  assert.equal(day(future), true);
  const partial = snapshot(); partial.page = { offset: 20, limit: 20, total: 21 }; partial.counts.recorded = 21;
  partial.currencies[0].counts.recorded = 21; partial.currencies[0].amounts_minor.recorded = "2184"; assert.equal(day(partial, 20), true);
  partial.currencies[0].amounts_minor.recorded = "103"; assert.equal(day(partial, 20), false);
  partial.currencies[0].amounts_minor.recorded = "9007199254740993"; assert.equal(day(partial, 20), false);
  const cancelled = snapshot(); cancelled.rows[0].original.cancellation = { id: "cancel", institute_id: "inst", commission_id: "commission",
    actor_id: "manager", reason: "Correction", idempotency_key: "cancel", created_at: "2026-10-25T12:00:00.000003Z" };
  cancelled.rows[0].state = "future_cancellation"; cancelled.counts.recorded = 0; cancelled.counts.future_cancellation = 1;
  cancelled.currencies[0].counts = { ...cancelled.counts }; cancelled.currencies[0].amounts_minor.recorded = "0";
  cancelled.currencies[0].amounts_minor.future_cancellation = "104"; assert.equal(day(cancelled), true);
  cancelled.generated_at = "2026-10-25T12:00:00.000003Z"; assert.equal(day(cancelled), false);
  cancelled.rows[0].state = "cancelled"; cancelled.counts.future_cancellation = 0; cancelled.counts.cancelled = 1;
  cancelled.currencies[0].counts = { ...cancelled.counts }; cancelled.currencies[0].amounts_minor.future_cancellation = "0";
  cancelled.currencies[0].amounts_minor.cancelled = "104"; assert.equal(day(cancelled), true);
  const duplicate = original(); duplicate.id = "second"; duplicate.idempotency_key = "second-key";
  assert.equal(validCommissionPage({ institute_id: "inst", employee_id: "emp", generated_at: snapshot().generated_at,
    page: { offset: 0, limit: 20, total: 2 }, rows: [original(), duplicate] }, "inst", "emp", 0), false);
  const empty = snapshot(); empty.rows = []; empty.page.total = 0; empty.counts = Object.fromEntries(commissionStates.map(k => [k, 0])) as typeof empty.counts;
  empty.currencies = []; assert.equal(day(empty), true);
});
