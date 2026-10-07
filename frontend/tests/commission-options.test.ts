import test from "node:test";
import assert from "node:assert/strict";
import { commissionSourceMinor, validCommissionSourceOptions, type CommissionSourceOptions } from "../src/commission-options";
import { rule, original, props } from "./commission-fixture";
function options(): CommissionSourceOptions {
  const calculation = original().calculation;
  return { institute_id: "inst", employee_id: "emp", rule: rule(), day: props.day, timezone: props.timezone,
    start: props.start, end: props.end, generated_at: calculation.source.captured_at, basis: "source_closed_day", complete_sources: false,
    page: { offset: 0, limit: 20, total: 1 }, rows: [{ line_id: "line", ticket_id: "ticket", service_id: "service", category: "care",
      quantity: 3, amount: "10.35", currency: "CHF", arrival_at: calculation.source.arrival_at, paid_at: calculation.source.paid_at,
      already_attributed: false, cancellation_clock_future: false, exclusion: null, calculation }] };
}
const valid = (v: unknown, selected = rule(), offset = 0) => validCommissionSourceOptions(v, "inst", selected, props.day, props.start, props.end, props.timezone, offset);
test("closed-source preview binds raw facts, exact decimal math, pinned rule and capture clock", () => {
  assert.equal(valid(options()), true);
  for (const mutate of [
    (r: CommissionSourceOptions) => { r.rows[0].amount = "10.36"; },
    (r: CommissionSourceOptions) => { r.rows[0].quantity = 4; },
    (r: CommissionSourceOptions) => { r.rows[0].ticket_id = "other"; },
    (r: CommissionSourceOptions) => { r.rows[0].calculation!.source.captured_at = "2026-10-25T12:00:00.000002Z"; },
    (r: CommissionSourceOptions) => { r.rows[0].calculation!.amount_minor = "103"; },
    (r: CommissionSourceOptions) => { r.rule.rate_basis_points = 2000; },
    (r: CommissionSourceOptions) => { r.complete_sources = true as false; },
    (r: CommissionSourceOptions) => { r.rows[0].paid_at = props.end; },
    (r: CommissionSourceOptions) => { r.rows.push(structuredClone(r.rows[0])); r.page.total = 2; },
    (r: CommissionSourceOptions) => { r.rows[0].amount = 10.35 as unknown as string; },
  ]) { const r = options(); mutate(r); assert.equal(valid(r), false); }
  const alias = options(); alias.rows[0].amount = "1.035E+1"; assert.equal(valid(alias), true);
  alias.rows[0].paid_at = "2026-10-25T12:00:00+01:00"; assert.equal(valid(alias), true);
  const named = rule(); named.service_id = "service";
  const r = options(); r.rule = named; r.rows[0].calculation!.terms.service_id = "service";
  assert.equal(valid(r, named), true); r.rows[0].service_id = "other"; assert.equal(valid(r, named), false);
});
test("source exclusions follow authoritative priority and cannot carry eligible previews", () => {
  const cases: [CommissionSourceOptions["rows"][number]["exclusion"], (r: CommissionSourceOptions) => void][] = [
    ["rule_cancelled", r => { r.rule.cancellation = { id: "cancel", institute_id: "inst", rule_id: "rule", actor_id: "manager", created_at: r.generated_at, reason: "Stop", idempotency_key: "cancel-key" }; r.rows[0].already_attributed = true; }],
    ["future_rule", r => { r.generated_at = "2026-10-25T09:00:00Z"; r.rows[0].already_attributed = true; }],
    ["already_attributed", r => { r.rows[0].already_attributed = true; r.rows[0].cancellation_clock_future = true; }],
    ["future_cancellation", r => { r.rows[0].cancellation_clock_future = true; r.rows[0].currency = "EUR"; }],
    ["future_closing", r => { r.generated_at = "2026-10-25T10:30:00Z"; }],
    ["currency_mismatch", r => { r.rows[0].currency = null; r.rows[0].amount = null; }],
    ["invalid_source", r => { r.rows[0].amount = "-1.00"; }],
    ["invalid_source", r => { r.rows[0].amount = "0.001"; }],
    ["invalid_source", r => { r.rows[0].quantity = null; }],
    ["invalid_source", r => { r.rows[0].arrival_at = null; }],
    ["invalid_source", r => { r.rows[0].arrival_at = "2026-10-25T11:00:00.000001Z"; }],
  ];
  for (const [exclusion, mutate] of cases) {
    const r = options(); mutate(r); r.rows[0].exclusion = exclusion;
    assert.equal(valid(r, r.rule), false); r.rows[0].calculation = null; assert.equal(valid(r, r.rule), true, exclusion!);
    r.rows[0].exclusion = null; assert.equal(valid(r, r.rule), false);
  }
  const r = options(); r.rule.first_day = r.rule.last_day = "2026-10-26";
  r.rule.period_start = props.end; r.rule.period_end = "2026-10-26T23:00:00Z";
  r.rows[0].calculation = null; r.rows[0].exclusion = "outside_period";
  assert.equal(valid(r, r.rule), true);
});
test("source pages retain unknown coverage and exact decimal boundary handling", () => {
  for (const [raw, expected] of [["0", 0n], ["-0.00", 0n], ["10.3500", 1035n], ["99999999.99", 9999999999n], ["1E+2", 10000n]] as const)
    assert.equal(commissionSourceMinor(raw), expected);
  for (const raw of [true, 10.35, "NaN", "Infinity", "-0.01", "0.001", "100000000", "1e999", "1e-999", " 1.00"])
    assert.equal(commissionSourceMinor(raw), undefined);
  const r = options(); r.page = { offset: 20, limit: 20, total: 21 };
  assert.equal(valid(r, rule(), 20), true); assert.equal(valid(r), false);
  r.page.total = 22; assert.equal(valid(r, rule(), 20), false);
  const empty = options(); empty.rows = []; empty.page.total = 0; assert.equal(valid(empty), true);
  empty.page.total = 1; assert.equal(valid(empty), false);
});
