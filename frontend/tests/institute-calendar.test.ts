import test from "node:test";
import assert from "node:assert/strict";
import { instituteInstants, instituteSlot, nextInstituteSlot } from "../src/institute-calendar";
import { instituteTimeline, timelineBlock } from "../src/planning-timeline";

test("institute wall clocks and mutations are independent of three workstation zones", () => {
  const previous = process.env.TZ;
  try {
    for (const host of ["UTC", "America/Los_Angeles", "Australia/Sydney"]) {
      process.env.TZ = host;
      assert.equal(instituteSlot("2026-10-06T22:30:00Z", "Europe/Zurich")!.date, "2026-10-07");
      assert.equal(instituteSlot("2026-10-06T22:30:00Z", "Europe/Zurich")!.time, "00:30");
      assert.deepEqual(instituteInstants("2026-10-07", "10:15", "Europe/Zurich"), ["2026-10-07T08:15:00.000Z"]);
      assert.equal(nextInstituteSlot("Europe/Zurich", Date.parse("2026-10-06T22:30:20Z")).time, "00:45");
    }
  } finally { if (previous === undefined) delete process.env.TZ; else process.env.TZ = previous; }
});

test("missing clocks, repeated clocks, half-hour transitions and invalid dates are explicit", () => {
  assert.deepEqual(instituteInstants("2026-03-29", "02:30", "Europe/Zurich"), []);
  assert.deepEqual(instituteInstants("2026-10-25", "02:30", "Europe/Zurich"), ["2026-10-25T00:30:00.000Z", "2026-10-25T01:30:00.000Z"]);
  assert.deepEqual(instituteInstants("2026-04-05", "01:45", "Australia/Lord_Howe"), ["2026-04-04T14:45:00.000Z", "2026-04-04T15:15:00.000Z"]);
  for (const [date, time] of [["2026-02-30", "10:00"], ["0000-01-01", "10:00"], ["2026-10-07", "24:00"], ["2026-10-07", "02:60"]]) assert.deepEqual(instituteInstants(date, time, "UTC"), []);
  assert.deepEqual(instituteInstants("2026-10-07", "10:00", "invalid/legacy"), ["2026-10-07T10:00:00.000Z"]);
  assert.equal(instituteSlot("2026-10-07T10:00:00", "UTC"), undefined);
});

test("elapsed timeline distinguishes both autumn occurrences and real interval duration", () => {
  const day = new Date("2026-10-25T01:30:00Z"), range = { startHour: 0, endHour: 5 }, zone = "Europe/Zurich";
  const window = instituteTimeline(range, day, zone)!;
  assert.equal(window.end - window.start, 6 * 3600000);
  assert.deepEqual(window.marks.filter(mark => mark.label.startsWith("02:00")).map(mark => mark.label), ["02:00 UTC+02:00", "02:00 UTC+01:00"]);
  const block = timelineBlock("2026-10-25T00:45:00Z", "2026-10-25T01:15:00Z", range, day, 1.6, zone)!;
  assert.ok(block.width > 8 && block.width < 9);
  const first = timelineBlock("2026-10-25T00:30:00Z", "2026-10-25T00:45:00Z", range, day, 1.6, zone)!;
  const second = timelineBlock("2026-10-25T01:30:00Z", "2026-10-25T01:45:00Z", range, day, 1.6, zone)!;
  assert.ok(second.left > first.left);
});

test("spring elapsed axis omits the skipped hour and resolves a skipped display boundary", () => {
  const day = new Date("2026-03-29T01:30:00Z"), zone = "Europe/Zurich";
  const whole = instituteTimeline({ startHour: 0, endHour: 5 }, day, zone)!;
  assert.equal(whole.end - whole.start, 4 * 3600000);
  assert.equal(whole.marks.some(mark => mark.label.startsWith("02:")), false);
  assert.equal(timelineBlock("2026-03-29T00:45:00Z", "2026-03-29T01:15:00Z", { startHour: 0, endHour: 5 }, day, 1.6, zone)!.width, 12.5);
  const window = instituteTimeline({ startHour: 2, endHour: 6 }, day, zone)!;
  assert.equal(window.marks[0].label, "03:00");
  assert.equal(window.end - window.start, 3 * 3600000);
});

test("institute-day clipping retains carryovers and excludes other civil days", () => {
  const day = new Date("2026-10-06T22:30:00Z"), range = { startHour: 0, endHour: 5 }, zone = "Europe/Zurich";
  assert.deepEqual(timelineBlock("2026-10-06T21:50:00Z", "2026-10-06T22:15:00Z", range, day, 1.6, zone), { left: 0, width: 5 });
  assert.equal(timelineBlock("2026-10-07T22:15:00Z", "2026-10-07T22:30:00Z", range, day, 1.6, zone), null);
  assert.equal(timelineBlock("2026-10-07T00:15:00", "2026-10-07T00:30:00", range, day, 1.6, zone), null);
  const end = instituteTimeline({ startHour: 22, endHour: 24 }, day, zone)!;
  assert.equal(end.marks.at(-1)!.label, "24:00");
});
