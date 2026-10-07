import test from "node:test";
import assert from "node:assert/strict";
import { validObjectivePage, matchesObjective, type ObjectivePage } from "../src/objective-utils";
export function snapshot(): ObjectivePage {
  return { institute_id: "inst", employee_id: "emp", generated_at: "2026-10-26T12:00:00Z", page: { offset: 0, limit: 20, total: 1 }, rows: [{
    objective: { id: "obj", institute_id: "inst", employee_id: "emp", actor_id: "manager", title: "Original target", metric: "closed_attributed_gross",
      currency: "CHF", target: "90071992547409.93", first_day: "2026-10-25", last_day: "2026-10-25", timezone: "Europe/Zurich",
      period_start: "2026-10-24T22:00:00Z", period_end: "2026-10-25T23:00:00Z", reason: "Declared", idempotency_key: "key",
      created_at: "2026-10-07T12:00:00Z", cancellation: null }, period_state: "ended", known_value: "90071992547409.93", value: "90071992547409.93",
    achieved: true, source_count: 1, missing_amount_sources: 0, unknown_currency_sources: 0, other_currency_sources: 0 }] };
}
const valid = (v: unknown) => validObjectivePage(v, "inst", "emp", 0);
test("objective read preserves exact target, pinned DST period and achievement", () => {
  const r = snapshot(); assert.equal(valid(r), true);
  assert.equal(matchesObjective(r.rows[0].objective, { ...r.rows[0].objective, target: "90071992547409.930" }, "manager"), true);
  for (const change of [
    (r: ObjectivePage) => { r.employee_id = "foreign"; }, (r: ObjectivePage) => { r.rows[0].objective.target = 10 as never; },
    (r: ObjectivePage) => { r.rows[0].value = "90071992547409.94"; }, (r: ObjectivePage) => { r.rows[0].achieved = false; },
    (r: ObjectivePage) => { r.rows[0].objective.period_start = "2026-10-25T00:00:00Z"; },
    (r: ObjectivePage) => { r.rows[0].objective.timezone = "UTC"; }, (r: ObjectivePage) => { r.page.total = 2; },
    (r: ObjectivePage) => { r.rows[0].period_state = "active"; }, (r: ObjectivePage) => { r.rows[0].other_currency_sources = 2; },
    (r: ObjectivePage) => { r.rows[0].source_count = 0; },
  ]) { const r = snapshot(); change(r); assert.equal(valid(r), false); }
});
test("unknown currency preserves known subtotal while cancellation never fabricates performance", () => {
  const r = snapshot(), p = r.rows[0]; p.source_count = 2; p.unknown_currency_sources = 1; p.value = null; p.achieved = null;
  assert.equal(valid(r), true); p.value = p.known_value; assert.equal(valid(r), false);
  p.objective.cancellation = { id: "cancel", objective_id: "obj", institute_id: "inst", actor_id: "manager", created_at: r.generated_at,
    reason: "Revised", idempotency_key: "cancel-key" }; p.period_state = "cancelled";
  Object.assign(p, { known_value: null, value: null, achieved: null, source_count: null, missing_amount_sources: null, unknown_currency_sources: null, other_currency_sources: null });
  assert.equal(valid(r), true); p.source_count = 0; assert.equal(valid(r), false);
});
test("completed-session progress counts only integer recorded sources", () => {
  const r = snapshot(), p = r.rows[0]; Object.assign(p.objective, { metric: "completed_sessions", currency: null, target: "1" });
  Object.assign(p, { known_value: "1", value: "1", achieved: true }); assert.equal(valid(r), true);
  p.value = "1.5"; assert.equal(valid(r), false); p.value = "1"; p.other_currency_sources = 1; assert.equal(valid(r), false);
});
test("pinned objective boundaries retain skipped adjacent days and never use the host clock", () => {
  const r = snapshot(), o = r.rows[0].objective;
  Object.assign(o, { first_day: "2011-12-29", last_day: "2011-12-29", timezone: "Pacific/Apia",
    period_start: "2011-12-29T10:00:00Z", period_end: "2011-12-30T10:00:00Z" });
  assert.equal(valid(r), true);
  Object.assign(o, { first_day: "2011-12-30", last_day: "2011-12-31", period_start: "2011-12-30T10:00:00Z", period_end: "2011-12-31T10:00:00Z" });
  assert.equal(valid(r), true);
});
