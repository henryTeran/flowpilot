import test from "node:test";
import assert from "node:assert/strict";

import { shouldOfferDelayedReleaseAction } from "./queue-utils.ts";

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
