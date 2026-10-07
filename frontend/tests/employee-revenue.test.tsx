import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import React, { act } from "react";
import { EmployeeRevenuePanel } from "../src/components/EmployeeRevenuePanel";
import { validEmployeeRevenue, revenueCents, type EmployeeRevenue } from "../src/employee-revenue-utils";
import { setAccessToken } from "../src/api/session";
const dom = new JSDOM("<!doctype html><div id='root'></div>", { url: "http://localhost:5173" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (role = "responsable_institut", sub = "manager") => `h.${Buffer.from(JSON.stringify({ role, sub })).toString("base64url")}.s`;
const response = (value: unknown) => new Response(JSON.stringify(value), { headers: { "Content-Type": "application/json" } });
const props = { institute: "inst", employee: "emp", day: "2026-10-25", start: "2026-10-24T22:00:00Z", end: "2026-10-25T23:00:00Z", timezone: "Europe/Zurich" };
function snapshot(): EmployeeRevenue {
  return { institute_id: "inst", employee_id: "emp", day: props.day, start: props.start, end: props.end, generated_at: "2026-10-26T12:00:00Z",
    page: { offset: 0, limit: 50, total: 1 }, rows: [{ id: "line", ticket_id: "ticket", ticket_number: "T-1", employee_id: "emp",
      service_id: "service", paid_at: "2026-10-25T00:30:00Z", currency: "CHF", category: "care", quantity: 1, amount: "90071992547409.93" }],
    currencies: [{ currency: "CHF", line_count: 1, ticket_count: 1, amount_known_total: "90071992547409.93", amount_missing_lines: 0, total: "90071992547409.93" }], institute_unattributed_lines: 1 };
}
const valid = (value: unknown) => validEmployeeRevenue(value, "inst", "emp", props.day, props.start, props.end, 0);

test("employee revenue preserves exact cents and rejects contradictory scope, units, totals and page facts", () => {
  assert.equal(valid(snapshot()), true); assert.equal(revenueCents("90071992547409.93"), 9007199254740993n);
  for (const corrupt of [
    (row: EmployeeRevenue) => { row.employee_id = "foreign"; }, (row: EmployeeRevenue) => { row.start = "2026-10-25T00:00:00Z"; },
    (row: EmployeeRevenue) => { row.rows[0].amount = 12 as never; }, (row: EmployeeRevenue) => { row.rows[0].paid_at = props.end; },
    (row: EmployeeRevenue) => { row.currencies[0].total = "1.00"; }, (row: EmployeeRevenue) => { row.currencies[0].currency = null; },
    (row: EmployeeRevenue) => { row.page.total = 2; }, (row: EmployeeRevenue) => { row.rows[0].amount = "90071992547409.94"; },
  ]) { const row = snapshot(); corrupt(row); assert.equal(valid(row), false); }
  const missing = snapshot(); missing.rows[0].amount = null; Object.assign(missing.currencies[0], { amount_known_total: "0.00", amount_missing_lines: 1, total: null });
  assert.equal(valid(missing), true);
});

test("native revenue hides a failed fresh read and displays exact money with original attribution", async () => {
  const fetch = globalThis.fetch, root = createRoot(document.getElementById("root")!); let corrupt = false, reads = 0;
  globalThis.fetch = async () => { reads++; const row = snapshot(); if (corrupt) row.currencies[0].total = "1.00"; return response(row); };
  try {
    setAccessToken(token("accueil")); await act(async () => root.render(<EmployeeRevenuePanel {...props} />)); assert.equal(reads, 0);
    setAccessToken(token()); await act(async () => root.render(<EmployeeRevenuePanel {...props} />));
    assert.match(document.body.textContent!, /90071992547409,93 CHF/); assert.match(document.body.textContent!, /sans exécutante enregistrée/);
    corrupt = true; await act(async () => document.querySelector<HTMLButtonElement>("button")!.click());
    assert.equal(document.querySelector("li"), null); assert.match(document.body.textContent!, /Lecture du CA attribué à vérifier/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = fetch; }
});

test("late revenue for an old employee or actor cannot expose old money", async () => {
  const fetch = globalThis.fetch, root = createRoot(document.getElementById("root")!); const pending: ((value: Response) => void)[] = [];
  globalThis.fetch = async () => new Promise(resolve => pending.push(resolve));
  try {
    setAccessToken(token()); await act(async () => root.render(<EmployeeRevenuePanel {...props} />));
    await act(async () => root.render(<EmployeeRevenuePanel {...props} employee="other" />));
    await act(async () => pending[0](response(snapshot()))); assert.doesNotMatch(document.body.textContent!, /900719925/);
    setAccessToken(token("responsable_institut", "new")); await act(async () => root.render(<EmployeeRevenuePanel {...props} />));
    await act(async () => pending[1](response(snapshot()))); assert.doesNotMatch(document.body.textContent!, /900719925/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = fetch; }
});
