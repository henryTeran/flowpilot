import test from "node:test";
import assert from "node:assert/strict";
import { validWorkHours, formatWorkDuration, type WorkHours } from "../src/work-hours-utils";
function snapshot(): WorkHours {
  return { institute_id: "inst", employee_id: "emp", day: "2025-10-26", timezone: "Europe/Zurich", start: "2025-10-25T22:00:00Z", end: "2025-10-26T23:00:00Z",
    generated_at: "2026-10-07T12:00:00Z", page: { offset: 0, limit: 20, total: 1 }, rows: [{ interval: { id: "wrk", institute_id: "inst", employee_id: "emp",
      start_time: "2025-10-26T00:30:00.000001Z", end_time: "2025-10-26T01:30:00.000002Z", created_at: "2026-10-07T00:00:00Z", actor_id: "manager", reason: "Declared", idempotency_key: "key", cancellation: null },
      clipped_start: "2025-10-26T00:30:00.000001Z", clipped_end: "2025-10-26T01:30:00.000002Z", duration_us: "3600000001", exclusion: null }],
    active_sources: 1, future_end_sources: 0, overlap_sources: 0, known_declared_duration_us: "3600000001", known_union_duration_us: "3600000001", recorded_duration_us: "3600000001", complete_attendance: false };
}
const valid = (r: unknown) => validWorkHours(r, "inst", "emp", "2025-10-26", snapshot().start, snapshot().end, "Europe/Zurich", 0);
test("work hours validate exact microseconds, source ownership and complete-page union", () => {
  assert.equal(valid(snapshot()), true); assert.equal(formatWorkDuration("3600000001"), "1 h 00 min 00,000001 s");
  for (const change of [
    (r: WorkHours) => { r.employee_id = "foreign"; }, (r: WorkHours) => { r.rows[0].interval.actor_id = ""; },
    (r: WorkHours) => { r.rows[0].duration_us = "3600000000"; }, (r: WorkHours) => { r.known_union_duration_us = "3600000000"; },
    (r: WorkHours) => { r.complete_attendance = true as never; }, (r: WorkHours) => { r.start = "2025-10-26T00:00:00Z"; },
    (r: WorkHours) => { r.rows[0].clipped_end = r.end; }, (r: WorkHours) => { r.page.total = 2; },
    (r: WorkHours) => { r.recorded_duration_us = 3600000001 as never; }, (r: WorkHours) => { r.rows[0].exclusion = "cancelled"; },
  ]) { const r = snapshot(); change(r); assert.equal(valid(r), false); }
});
test("cancelled/future sources cannot invent hours and an empty ledger remains unknown", () => {
  const r = snapshot(); r.generated_at = "2020-01-01T00:00:00Z"; r.future_end_sources = 1; r.rows[0].exclusion = "future_end";
  r.known_declared_duration_us = r.known_union_duration_us = "0"; r.recorded_duration_us = null; assert.equal(valid(r), true);
  r.recorded_duration_us = "0"; assert.equal(valid(r), false); r.recorded_duration_us = null;
  r.rows[0].interval.cancellation = { id: "cancel", institute_id: "inst", work_interval_id: "wrk", actor_id: "manager", created_at: "2026-10-07T00:00:00Z", reason: "Revised", idempotency_key: "cancel" };
  r.rows[0].exclusion = "cancelled"; r.active_sources = r.future_end_sources = 0; assert.equal(valid(r), true);
  r.page.total = 0; r.rows = []; assert.equal(valid(r), true);
});
test("native hours validate an overlap union against original microsecond sources", () => {
  const r = snapshot(), second = structuredClone(r.rows[0]); second.interval.id = "second";
  second.interval.start_time = second.clipped_start = "2025-10-26T01:00:00.000001Z";
  second.interval.end_time = second.clipped_end = "2025-10-26T02:00:00.000002Z";
  r.rows.push(second); r.page.total = r.active_sources = 2; r.overlap_sources = 1;
  r.known_declared_duration_us = "7200000002"; r.known_union_duration_us = r.recorded_duration_us = "5400000001";
  assert.equal(valid(r), true); r.rows.reverse(); assert.equal(valid(r), false);
});
