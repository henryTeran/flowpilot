import test from "node:test";
import assert from "node:assert/strict";
import { validReturnRead, type ReturnRead } from "../src/crm-return-utils";
const start = "2026-10-06T00:00:00Z", end = "2026-10-07T00:00:00Z";
function sample(): ReturnRead {
  return { complete_execution_coverage: false, complete_service_coverage: false, diagnostics: { unlinked_ticket: 0, invalid_owner_or_service: 0, invalid_actual_times: 0 },
    summary: { window: { institute_id: "i", customer_id: "customer_a", start, end, captured_at: end }, basis: "recorded_completed_ticket_care",
      execution_count: 3, episode_count: 2, known_gap_count: 1, overlapping_gap_count: 0, known_gap_total_us: "19",
      average_return_gap_us: { numerator: "19", denominator: "1" }, complete_customer_history: false, inferred_booking_credit: false },
    page: { offset: 0, limit: 20, total: 2 }, episodes: [
      { ticket_id: "t1", started_at: "2026-10-06T00:00:00Z", completed_at: "2026-10-06T00:00:00.000030Z", execution_count: 2, service_ids: ["a", "b"] },
      { ticket_id: "t2", started_at: "2026-10-06T00:00:00.000049Z", completed_at: "2026-10-06T00:00:00.000060Z", execution_count: 1, service_ids: ["a"] } ],
    gaps: [{ previous_ticket_id: "t1", next_ticket_id: "t2", gap_us: "19", quality: "known" }] };
}
const valid = (v: unknown, offset=0) => validReturnRead(v, "i", "customer_a", start, end, offset);
test("whole-cohort return guards independently verify exact gaps, mean and scope", () => {
  assert.equal(valid(sample()), true);
  for (const mutate of [(r: ReturnRead) => { r.gaps[0].gap_us = "20"; },
    (r: ReturnRead) => { r.summary.average_return_gap_us!.numerator = "20"; },
    (r: ReturnRead) => { r.summary.known_gap_count = 2; }, (r: ReturnRead) => { r.summary.execution_count = 4; },
    (r: ReturnRead) => { r.episodes[1].ticket_id = "t1"; }, (r: ReturnRead) => { r.episodes[0].service_ids = ["a", "a"]; },
    (r: ReturnRead) => { r.episodes[1].completed_at = end; }, (r: ReturnRead) => { r.summary.window.customer_id = "other"; },
    (r: ReturnRead) => { r.page.total = 3; }]) { const r = sample(); mutate(r); assert.equal(valid(r), false); }
  assert.equal(validReturnRead(sample(), "i", "customer_a", "2026-10-06T02:00:00+02:00", end), true);
  assert.equal(valid(null), false);
});
test("diagnostics and overlapping care preserve indeterminate means", () => {
  const r = sample(); r.diagnostics.invalid_actual_times = 1;
  assert.equal(valid(r), false); r.summary.average_return_gap_us = null; assert.equal(valid(r), true);
  const overlap = sample(); overlap.episodes[1].started_at = "2026-10-06T00:00:00.000020Z";
  overlap.gaps[0].quality = "overlapping_episodes"; overlap.gaps[0].gap_us = null;
  overlap.summary.known_gap_count = 0; overlap.summary.overlapping_gap_count = 1; overlap.summary.known_gap_total_us = "0";
  overlap.summary.average_return_gap_us = null; assert.equal(valid(overlap), true);
  overlap.gaps[0].quality = "known"; overlap.gaps[0].gap_us = "0"; assert.equal(valid(overlap), false);
});
test("partial pages retain global metrics without guessing the off-page predecessor", () => {
  const r = sample(); r.page.offset = 1; r.episodes = [r.episodes[1]];
  assert.equal(valid(r,1), true); r.gaps[0].previous_ticket_id = "t2"; assert.equal(valid(r,1), false);
  const impossible = sample(); impossible.page.offset = 3; impossible.page.total = impossible.summary.episode_count = 3;
  impossible.summary.known_gap_count = 2; impossible.summary.known_gap_total_us = "86400000001";
  impossible.summary.average_return_gap_us = { numerator: "86400000001", denominator: "2" };
  impossible.episodes = []; impossible.gaps = [];
  assert.equal(valid(impossible,3), false);
  const empty = sample(); empty.summary.execution_count = empty.summary.episode_count = empty.summary.known_gap_count = 0;
  empty.summary.known_gap_total_us = "0"; empty.summary.average_return_gap_us = null; empty.page.total = 0; empty.episodes = []; empty.gaps = [];
  assert.equal(valid(empty), true);
});
