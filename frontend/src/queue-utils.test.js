import test from "node:test";
import assert from "node:assert/strict";

import { shouldOfferDelayedReleaseAction, compareQueueArrival, createArrivalIntent } from "./queue-utils.ts";

test("queue order uses arrival and id even when estimates or assignment differ", () => {
  const rows = [
    { id: "b", arrival_time: "2026-10-02T09:00:00Z", status: "waiting", estimated_start_time: "2026-10-02T08:00:00Z" },
    { id: "a", arrival_time: "2026-10-02T09:00:00Z", status: "assigned" },
    { id: "z", arrival_time: "2026-10-02T08:59:00Z", status: "waiting" },
  ];
  assert.deepEqual(rows.sort(compareQueueArrival).map((row) => row.id), ["z", "a", "b"]);
});

test("an arrival retry keeps its key and a new arrival or changed selection gets a new key", () => {
  const intent = createArrivalIntent();
  const payload = { institute_id: "i", service_ids: ["a", "b"] };
  const first = intent.keyFor(payload);
  assert.equal(intent.keyFor({ ...payload, service_ids: ["b", "a"] }), first);
  assert.notEqual(intent.keyFor({ ...payload, institute_id: "other" }), first);
  const second = intent.keyFor(payload);
  intent.complete();
  assert.notEqual(intent.keyFor(payload), second);
});

test("offers quick release for a delayed employee tied to an active ticket", () => {
  const ticket = { status: "in_progress", assigned_employee_id: "emp-1" };
  const employee = { id: "emp-1", status: "delayed" };

  assert.equal(shouldOfferDelayedReleaseAction(ticket, employee), true);
});

test("does not offer release when the employee is already available", () => {
  const ticket = { status: "in_progress", assigned_employee_id: "emp-1" };
  const employee = { id: "emp-1", status: "available" };

  assert.equal(shouldOfferDelayedReleaseAction(ticket, employee), false);
});
