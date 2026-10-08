import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { validWalkInCancellations } from "../src/revenue-walk-in-utils";
import { revenueOriginalFingerprint } from "../src/revenue-scenario-utils";
const vector = JSON.parse(readFileSync(new URL("./fixtures/revenue-walk-in-14t.json", import.meta.url), "utf8"));
const period = { start: vector.window.start, end: vector.window.end };
test("retained walk-in commercial values preserve backend raw SHA, zero and separate uncertain currencies", async () => {
  assert.equal(await validWalkInCancellations(vector, "own", period, 0), true);
  assert.equal(vector.opportunities[1].estimated_value.amount_minor, "0");
  assert.equal(vector.opportunities[4].estimated_value, null);
  for (const mutate of [
    (r: any) => { r.cancelled_revenue = "0"; }, (r: any) => { r.causal_loss_proven = 0; }, (r: any) => { r.window.institute_id = "foreign"; },
    (r: any) => { r.legacy_unpriced_count = 0; }, (r: any) => { r.page.limit = 50; }, (r: any) => { r.opportunities[0].action_executed = true; },
    (r: any) => { r.opportunities[0].evidence.occurred_at = r.window.end; }, (r: any) => { r.opportunities[1].evidence.event_id = 1; },
    (r: any) => { r.opportunities[0].evidence.original.terms.actor_id = "Changed"; }, (r: any) => { r.opportunities[0].estimated_value.amount_minor = "999"; },
    (r: any) => { r.opportunities[6].estimated_value = r.opportunities[0].estimated_value; },
    (r: any) => { r.retained_amounts[1].known_gross_minor = "988"; },
  ]) { const bad = structuredClone(vector); mutate(bad); assert.equal(await validWalkInCancellations(bad, "own", period, 0), false); }
  for (const mutate of [
    (t: any) => { t.realized_revenue = true; }, (t: any) => { t.ticket_id = "foreign"; }, (t: any) => { t.previous_status = "paid"; },
    (t: any) => { t.lines[0].quantity = 0; }, (t: any) => { t.lines[0].removed_at = "2026-01-03T00:00:00Z"; },
    (t: any) => { t.lines.push(t.lines[0]); }, (t: any) => { t.lines[0].unit_minor = null; }, (t: any) => { t.ignored = true; },
  ]) { const bad = structuredClone(vector), saved = bad.opportunities[0].evidence.original; mutate(saved.terms); saved.fingerprint = await revenueOriginalFingerprint(saved.terms); assert.equal(await validWalkInCancellations(bad, "own", period, 0), false); }
});
test("actual page cardinality and partial returned evidence cannot overstate whole-cohort retained totals", async () => {
  const r = structuredClone(vector), rows = [];
  for (let n = 0; n < 25; n++) { const o = structuredClone(vector.opportunities[1]); o.evidence.event_id = n+1; o.evidence.ticket_id = `ticket-${n}`; o.evidence.original.terms.ticket_id = o.evidence.ticket_id; o.evidence.original.fingerprint = await revenueOriginalFingerprint(o.evidence.original.terms); rows.push(o); }
  r.page.total = 25; r.retained_terms_count = 25; r.legacy_unpriced_count = 0;
  r.retained_amounts = [{ currency: "CHF", source_count: 25, known_amount_count: 25, missing_amount_count: 0, invalid_amount_count: 0, known_gross_minor: "0", complete_gross_minor: "0", average_minor: { numerator: "0", denominator: "25" } }];
  r.opportunities = rows.slice(0,20); assert.equal(await validWalkInCancellations(r, "own", period, 0), true);
  r.page.offset = 20; r.opportunities = rows.slice(20); assert.equal(await validWalkInCancellations(r, "own", period, 20), true);
  r.opportunities.pop(); assert.equal(await validWalkInCancellations(r, "own", period, 20), false);
});
