import test from "node:test";
import assert from "node:assert/strict";
import { original, props } from "./rebooking-fixture";
import { validSourceChoices, validTargetChoices, type SourceChoices, type TargetChoices } from "../src/rebooking-options";
import { sources, targets } from "./rebooking-options-fixture";
const validSources = (r: unknown) => validSourceChoices(r, "inst", "emp", props.day, props.start, props.end, props.timezone, 0);
const validTargets = (r: unknown) => validTargetChoices(r, "inst", original().source_capture, 0);
test("source choices verify exact execution capture, ownership and disabled exclusion priority", () => {
  assert.equal(validSources(sources()), true);
  for (const corrupt of [
    (r: SourceChoices) => { r.employee_id = "foreign"; }, (r: SourceChoices) => { r.basis = "declaration_recorded_at" as never; },
    (r: SourceChoices) => { r.complete_sources = true as never; }, (r: SourceChoices) => { r.rows[0].customer_known = false; },
    (r: SourceChoices) => { r.rows[0].capture!.actual_end = "2026-10-07T11:00:00.000001Z"; },
    (r: SourceChoices) => { r.rows[0].already_attributed = true; }, (r: SourceChoices) => { r.rows[0].actual_end = props.end; },
    (r: SourceChoices) => { r.rows[0].actual_start = null; },
  ]) { const r = sources(); corrupt(r); assert.equal(validSources(r), false); }
  const r = sources(); r.rows[0].already_attributed = true; r.rows[0].exclusion = "already_attributed"; r.rows[0].capture = null; assert.equal(validSources(r), true);
  r.rows[0].customer_known = false; r.rows[0].exclusion = "unknown_customer"; assert.equal(validSources(r), true);
  r.generated_at = "2026-10-07T10:59:59.999999Z"; r.rows[0].exclusion = "future_end"; assert.equal(validSources(r), true);
});
test("target choices pin selected execution and original creation without assuming attendance or target performer", () => {
  assert.equal(validTargets(targets()), true);
  for (const corrupt of [
    (r: TargetChoices) => { r.source.customer_id = "other"; }, (r: TargetChoices) => { r.source.actual_end = "2026-10-07T11:00:00.000001Z"; },
    (r: TargetChoices) => { r.rows[0].creation_events = 2; }, (r: TargetChoices) => { r.rows[0].capture!.created_at = "2026-10-07T10:59:59.999999Z"; },
    (r: TargetChoices) => { r.rows[0].capture!.current_start = "2026-10-08T12:00:00.000001Z"; },
    (r: TargetChoices) => { r.rows[0].customer_id = "other"; }, (r: TargetChoices) => { r.rows[0].already_attributed = true; },
  ]) { const r = targets(); corrupt(r); assert.equal(validTargets(r), false); }
  const r = targets(); r.rows[0].creation_events = 0; r.rows[0].capture = null; r.rows[0].exclusion = "invalid_booking"; assert.equal(validTargets(r), true);
  r.rows[0].already_attributed = true; r.rows[0].exclusion = "already_attributed"; assert.equal(validTargets(r), true);
});
