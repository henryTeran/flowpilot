import test from "node:test";
import assert from "node:assert/strict";

import { resolveNextCheckoutTicket, resolveSessionCheckoutTicket } from "./checkout-utils.ts";

test("prefers the current employee checkout ticket before the next available ticket", () => {
  const tickets = [
    { id: "t-1", assigned_employee_id: "e-2", status: "ready_for_checkout" },
    { id: "t-2", assigned_employee_id: "e-1", status: "ready_for_checkout" },
    { id: "t-3", assigned_employee_id: "e-3", status: "in_checkout" },
  ];

  assert.equal(resolveNextCheckoutTicket(tickets, "e-1")?.id, "t-2");
});

test("falls back to the first available checkout ticket when the employee has no queue item", () => {
  const tickets = [
    { id: "t-1", assigned_employee_id: "e-2", status: "ready_for_checkout" },
    { id: "t-2", assigned_employee_id: "e-3", status: "in_checkout" },
  ];

  assert.equal(resolveNextCheckoutTicket(tickets, "e-1")?.id, "t-1");
});

test("finish and checkout selects the exact session ticket despite older completed employee tickets", () => {
  const finished = { id: "session", institute_id: "ours", status: "completed", ticket_line_id: "line-new" };
  const tickets = [
    { id: "old", institute_id: "ours", status: "ready_for_checkout", lines: [{ id: "line-old" }] },
    { id: "foreign", institute_id: "other", status: "ready_for_checkout", lines: [{ id: "line-new" }] },
    { id: "new", institute_id: "ours", status: "ready_for_checkout", lines: [{ id: "line-new" }] },
  ];
  assert.equal(resolveSessionCheckoutTicket(tickets, finished, "session", "ours")?.id, "new");
  assert.equal(resolveSessionCheckoutTicket(tickets.slice(0, 2), finished, "session", "ours"), undefined);
  assert.equal(resolveSessionCheckoutTicket(tickets, { ...finished, id: "stale" }, "session", "ours"), undefined);
  assert.equal(resolveSessionCheckoutTicket(tickets, { ...finished, status: "in_progress" }, "session", "ours"), undefined);
});
