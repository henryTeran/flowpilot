import test from "node:test";
import assert from "node:assert/strict";
import { formatInstituteTime, instituteTimeZone } from "../src/institute-time";

test("cashier hours use the institute independently of the workstation zone", () => {
  const previous = process.env.TZ;
  try {
    for (const host of ["UTC", "America/Los_Angeles", "Australia/Sydney"]) {
      process.env.TZ = host;
      assert.equal(formatInstituteTime("2026-10-06T06:15:00Z", "Europe/Zurich"), "08:15");
      assert.equal(formatInstituteTime("2026-10-06T08:15:00+02:00", "Europe/Zurich"), "08:15");
    }
  } finally { if (previous === undefined) delete process.env.TZ; else process.env.TZ = previous; }
});

test("daylight saving changes preserve the actual instant", () => {
  assert.equal(formatInstituteTime("2026-10-25T00:30:00Z", "Europe/Zurich"), "02:30");
  assert.equal(formatInstituteTime("2026-10-25T01:30:00Z", "Europe/Zurich"), "02:30");
  assert.equal(formatInstituteTime("2026-10-25T02:30:00Z", "Europe/Zurich"), "03:30");
});

test("unknown zones use visible UTC and ambiguous or invalid instants are unavailable", () => {
  assert.equal(instituteTimeZone("unknown/zone"), "UTC");
  assert.equal(formatInstituteTime("2026-10-06T06:15:00Z", "unknown/zone"), "06:15");
  for (const value of [null, undefined, "bad", "2026-10-06T06:15:00", "2026-99-99T99:99:99Z"]) {
    assert.equal(formatInstituteTime(value, "Europe/Zurich"), "—");
  }
});
