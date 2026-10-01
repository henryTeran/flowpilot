import test from "node:test";
import assert from "node:assert/strict";

import { resolveNextCheckoutTicket } from "./checkout-utils.ts";

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
