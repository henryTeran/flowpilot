import test from "node:test";
import assert from "node:assert/strict";
import { validOccupation, type Occupation } from "../src/occupation-utils";
import { props, snapshot } from "./occupation-fixture";
const valid = (r: unknown) => validOccupation(r, props.institute, props.employee, props.day, props.start, props.end, props.timezone, 0);
test("occupation verifies originals, microsecond union and intersection rather than accepting a plausible ratio", () => {
  assert.equal(valid(snapshot()), true);
  for (const corrupt of [
    (r: Occupation) => { r.work_hours.employee_id = "foreign"; },
    (r: Occupation) => { r.complete_activity = true as never; },
    (r: Occupation) => { r.rows[0].duration_us = "7200000001"; },
    (r: Occupation) => { r.rows[0].status = "planned"; },
    (r: Occupation) => { r.rows[0].clipped_start = "2025-10-26T02:00:00.000001Z"; },
    (r: Occupation) => { r.known_busy_duration_us = "7200000002"; r.outside_recorded_work_duration_us = "3600000001"; },
    (r: Occupation) => { r.covered_busy_duration_us = "3600000000"; r.outside_recorded_work_duration_us = "3600000001"; },
    (r: Occupation) => { r.rows[1].actual_start = null; },
    (r: Occupation) => { r.rows[1] = r.rows[0]; },
  ]) { const r = snapshot(); corrupt(r); assert.equal(valid(r), false); }
});
test("unfinished original is excluded and makes the recorded ratio unknown", () => {
  const r = snapshot();
  r.rows[1] = { ...r.rows[1], actual_end: null, status: "in_progress", exclusion: "missing_end", clipped_start: null, clipped_end: null, duration_us: null };
  r.diagnostics.retained = 1; r.diagnostics.missing_end = 1;
  r.known_busy_duration_us = "7200000000"; r.covered_busy_duration_us = "3600000000"; r.recorded_occupation_basis_points = null;
  assert.equal(valid(r), true);
  r.recorded_occupation_basis_points = "5000"; assert.equal(valid(r), false);
});
