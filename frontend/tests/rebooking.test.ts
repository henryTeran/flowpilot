import test from "node:test";
import assert from "node:assert/strict";
import { original, props, snapshot } from "./rebooking-fixture";
import { validRebooking, validRebookingDay, sameRebookingOriginal, validRebookingIntent, type RebookingDay } from "../src/rebooking-utils";
const valid = (r: unknown, offset = 0) => validRebookingDay(r, props.institute, props.employee, props.day, props.start, props.end, props.timezone, offset);
test("rebooking verifies pinned provenance and refuses forged day counts or return states", () => {
  assert.equal(valid(snapshot()), true);
  for (const corrupt of [
    (r: RebookingDay) => { r.employee_id = "foreign"; }, (r: RebookingDay) => { r.basis = "execution_day" as never; },
    (r: RebookingDay) => { r.complete_attribution = true as never; }, (r: RebookingDay) => { r.conversion_basis_points = "10000" as never; },
    (r: RebookingDay) => { r.rows[0].original.source_capture.employee_id = "foreign"; },
    (r: RebookingDay) => { r.rows[0].original.booking_capture.created_at = "2026-10-07T10:59:59.999999Z"; },
    (r: RebookingDay) => { r.rows[0].original.created_at = props.start; },
    (r: RebookingDay) => { r.rows[0].target_customer_id = "other"; },
    (r: RebookingDay) => { r.rows[0].state = "completed_return"; r.counts.booked_return = 0; r.counts.completed_return = 1; },
    (r: RebookingDay) => { r.counts.booked_return = 0; r.counts.no_show = 1; },
    (r: RebookingDay) => { r.counts.booked_return = Number.MAX_SAFE_INTEGER+1; },
  ]) { const r = snapshot(); corrupt(r); assert.equal(valid(r), false); }
});
test("rebooking independently checks actual return chronology and preserves unknown/cancelled priority", () => {
  const r = snapshot(), row = r.rows[0]; row.target_status = "completed"; row.actual_start = "2026-10-07T11:10:00Z"; row.actual_end = "2026-10-07T11:50:00Z";
  row.state = "completed_return"; r.counts.booked_return = 0; r.counts.completed_return = 1; assert.equal(valid(r), true);
  for (const [first, last] of [["2026-10-07T10:59:59Z", row.actual_end], [row.actual_start, "2026-10-07T12:00:00.000001Z"], [null, row.actual_end]]) {
    row.actual_start = first; row.actual_end = last; row.state = "unknown_target"; r.counts.completed_return = 0; r.counts.unknown_target = 1; assert.equal(valid(r), true);
  }
  r.generated_at = "2026-10-07T11:59:59.999999Z"; row.state = "future_recording"; r.counts.unknown_target = 0; r.counts.future_recording = 1; assert.equal(valid(r), true);
  row.original.cancellation = { id: "cancel", institute_id: "inst", rebooking_id: "original", actor_id: "manager", reason: "Correction", idempotency_key: "cancel-key", created_at: "2020-01-01T00:00:00Z" };
  row.state = "cancelled_declaration"; r.counts.future_recording = 0; r.counts.cancelled_declaration = 1; assert.equal(valid(r), true);
});
test("rebooking recovery compares all pinned instants exactly and permits retained cancelled history on partial pages", () => {
  const a = original(), b = original(); assert.equal(validRebooking(a, "inst", "emp"), true); assert.equal(sameRebookingOriginal(a, b), true);
  b.source_capture.actual_start = "2026-10-07T10:00:00.000001Z"; assert.equal(validRebooking(b, "inst"), true); assert.equal(sameRebookingOriginal(a, b), false);
  const r = snapshot(); r.page.total = 21; r.counts.booked_return = 0; r.counts.cancelled_declaration = 21;
  r.rows = Array.from({ length: 20 }, (_, i) => { const o = original(); o.id = `original-${i}`;
    o.cancellation = { id: `cancel-${i}`, institute_id: "inst", rebooking_id: o.id, actor_id: "manager", reason: "Correction", idempotency_key: `cancel-key-${i}`, created_at: "2026-10-07T12:00:00Z" };
    return { ...snapshot().rows[0], original: o, state: "cancelled_declaration" as const }; });
  assert.equal(valid(r), true);
  assert.equal(validRebookingIntent({ type: "cancel", original: r.rows[0].original, terms: { reason: "Correction", idempotency_key: "key" } }, "inst"), false);
  r.rows[0].original.cancellation = null; r.rows[0].state = "booked_return"; r.counts.booked_return = 1; r.counts.cancelled_declaration = 20; assert.equal(valid(r), true);
  r.rows[1].original.cancellation = null; r.rows[1].state = "booked_return"; r.counts.booked_return = 2; r.counts.cancelled_declaration = 19; assert.equal(valid(r), false);
});
