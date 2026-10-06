import test from "node:test";
import assert from "node:assert/strict";
import { timelineBlock } from "../src/planning-timeline";

test("sessions and appointments crossing midnight remain clipped to their visible day", () => {
  const day = new Date(2026, 9, 6, 23, 41), range = { startHour: 22, endHour: 24 };
  const start = new Date(2026, 9, 6, 23, 41).toISOString();
  const end = new Date(2026, 9, 7, 0, 1).toISOString();
  for (const minimum of [1.25, 1.6]) {
    const block = timelineBlock(start, end, range, day, minimum)!;
    assert.ok(block && block.left > 80 && block.width > 15);
    assert.equal(block.left + block.width, 100);
  }
});

test("prior-day carryovers and future-day appointments are distinguished from today's clock hours", () => {
  const day = new Date(2026, 9, 7, 1), range = { startHour: 0, endHour: 5 };
  const iso = (date: number, hour: number, minute = 0) => new Date(2026, 9, date, hour, minute).toISOString();
  assert.deepEqual(timelineBlock(iso(6, 23, 50), iso(7, 0, 15), range, day, 1.6), { left: 0, width: 5 });
  assert.equal(timelineBlock(iso(8, 1), iso(8, 2), range, day, 1.6), null);
  assert.equal(timelineBlock(iso(6, 1), iso(6, 2), range, day, 1.6), null);
});

test("daytime intervals preserve position while invalid intervals and edge overflow are rejected", () => {
  const day = new Date(2026, 9, 6, 12), range = { startHour: 9, endHour: 20 };
  const iso = (hour: number, minute = 0) => new Date(2026, 9, 6, hour, minute).toISOString();
  const block = timelineBlock(iso(10), iso(11), range, day, 1.25)!;
  assert.equal(block.left, 100 / 11); assert.equal(block.width, 100 / 11);
  const edge = timelineBlock(iso(19, 59), iso(20, 1), range, day, 1.6)!;
  assert.equal(edge.left + edge.width, 100);
  for (const [start, end] of [["invalid", iso(11)], [iso(11), iso(10)], [iso(10), iso(10)]]) assert.equal(timelineBlock(start, end, range, day, 1.25), null);
});
