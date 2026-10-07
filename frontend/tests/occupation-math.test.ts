import test from "node:test";
import assert from "node:assert/strict";
import { validOccupationTotals, formatOccupationBasisPoints, type OccupationTotals } from "../src/occupation-math";
const counts = { retained: 2, missing_start: 0, missing_end: 0, invalid_interval: 0, future_end: 0, unfinalized: 0 };
const totals: OccupationTotals = { known_busy_duration_us: "7200000001", covered_busy_duration_us: "3600000001",
  outside_recorded_work_duration_us: "3600000000", recorded_occupation_basis_points: "5000", complete_activity: false };
test("occupation compares exact recorded numerator/denominator and conserves outside time", () => {
  assert.equal(validOccupationTotals(totals, "7200000000", "7200000000", counts, 2), true);
  assert.equal(formatOccupationBasisPoints("5000"), "50,00 %");
  for (const change of [{ recorded_occupation_basis_points: "5001" }, { covered_busy_duration_us: "7200000001" },
    { outside_recorded_work_duration_us: "3600000001" }, { complete_activity: true }, { known_busy_duration_us: 7200000001 }]) {
    assert.equal(validOccupationTotals({ ...totals, ...change }, "7200000000", "7200000000", counts, 2), false);
  }
});
test("unknown hours or execution cannot become a zero occupation percentage", () => {
  const unknown = { ...totals, recorded_occupation_basis_points: null };
  assert.equal(validOccupationTotals(unknown, null, "7200000000", counts, 2), true);
  assert.equal(validOccupationTotals(totals, null, "7200000000", counts, 2), false);
  assert.equal(validOccupationTotals(unknown, "7200000000", "7200000000", { ...counts, missing_end: 1 }, 3), true);
  assert.equal(validOccupationTotals(totals, "7200000000", "7200000000", { ...counts, missing_end: 1 }, 3), false);
  assert.equal(validOccupationTotals(unknown, null, "7200000000", { ...counts, retained: -1 }, 2), false);
});
