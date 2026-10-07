import test from "node:test";
import assert from "node:assert/strict";
import React, { act } from "react";
import { JSDOM } from "jsdom";
import { capacityDayWindow, validRevenueCapacity, type RevenueCapacity } from "../src/revenue-capacity-utils";
import { RevenueCapacityReport } from "../src/components/RevenueCapacityReport";
import { setAccessToken } from "../src/api/session";
import { props, snapshot } from "./occupation-fixture";
function report(): RevenueCapacity {
  const evidence = snapshot(); evidence.page.limit = 1; evidence.rows = evidence.rows.slice(0, 1);
  const ratio = { numerator: "3600000001", denominator: "7200000000" };
  return { window: { institute_id: "inst", start: props.start, end: props.end, captured_at: evidence.work_hours.generated_at },
    day: props.day, timezone: props.timezone, basis: "declared_work_intersected_with_finalized_recorded_activity",
    page: { offset: 0, limit: 20, total: 1 }, rows: [{ employee_id: "emp", evidence, recorded_unoccupied_duration_us: "3599999999", recorded_utilization_ratio: ratio }],
    employee_count: 1, employees_without_usable_hours: 0, employees_with_uncertain_activity: 0,
    known_declared_union_duration_us: "7200000000", known_covered_busy_duration_us: "3600000001", known_outside_declared_work_duration_us: "3600000000",
    recorded_unoccupied_duration_us: "3599999999", recorded_utilization_ratio: ratio,
    complete_attendance: false, complete_activity: false, physical_unused_capacity: null, bookable_capacity: null, estimated_value: null };
}
const valid = (v: unknown, offset = 0) => validRevenueCapacity(v, "inst", props.day, props.timezone, offset);
test("recorded capacity verifies 25-hour day, pinned evidence, exact totals and unavailable physical claims", () => {
  assert.equal(valid(report()), true);
  const window = capacityDayWindow(props.day, props.timezone)!;
  assert.equal(window.start, "2025-10-25T22:00:00.000Z"); assert.equal(window.end, "2025-10-26T23:00:00.000Z");
  assert.equal(capacityDayWindow("2025-02-30", props.timezone), undefined);
  assert.equal(capacityDayWindow(props.day, "Invalid/Zone"), undefined);
  for (const corrupt of [
    (r: RevenueCapacity) => { r.window.institute_id = "foreign"; },
    (r: RevenueCapacity) => { r.window.captured_at = r.window.start; },
    (r: RevenueCapacity) => { r.rows[0].evidence.work_hours.generated_at = "2026-10-06T12:00:00Z"; },
    (r: RevenueCapacity) => { r.complete_activity = 0 as never; },
    (r: RevenueCapacity) => { r.bookable_capacity = "1" as never; },
    (r: RevenueCapacity) => { r.recorded_unoccupied_duration_us = "3600000000"; },
    (r: RevenueCapacity) => { r.recorded_utilization_ratio!.numerator = "3600000000"; },
    (r: RevenueCapacity) => { r.employee_count = 2; },
    (r: RevenueCapacity) => { r.rows[0].evidence.page.limit = 20; },
    (r: RevenueCapacity) => { r.rows[0].evidence.rows[0].duration_us = "1"; },
  ]) { const r = report(); corrupt(r); assert.equal(valid(r), false); }
});
test("all-employee totals remain independent of returned pages and off-page uncertainty hides utilization", () => {
  const r = report(), original = r.rows[0];
  r.employee_count = r.page.total = 25; r.rows = Array.from({ length: 20 }, (_, i) => {
    const row = structuredClone(original), id = `emp-${String(i).padStart(2, "0")}`;
    row.employee_id = row.evidence.work_hours.employee_id = row.evidence.work_hours.rows[0].interval.employee_id = id;
    return row;
  });
  r.known_declared_union_duration_us = String(7200000000n*25n);
  r.known_covered_busy_duration_us = String(3600000001n*25n);
  r.known_outside_declared_work_duration_us = String(3600000000n*25n);
  r.recorded_unoccupied_duration_us = String(3599999999n*25n);
  r.recorded_utilization_ratio = { numerator: r.known_covered_busy_duration_us, denominator: r.known_declared_union_duration_us };
  assert.equal(valid(r), true);
  r.employees_with_uncertain_activity = 1; r.recorded_unoccupied_duration_us = null; r.recorded_utilization_ratio = null;
  assert.equal(valid(r), true); // The uncertain employee can be outside this page.
  r.recorded_unoccupied_duration_us = "0"; assert.equal(valid(r), false);
  r.recorded_unoccupied_duration_us = null; r.rows[1] = r.rows[0]; assert.equal(valid(r), false);
});
const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (role = "responsable_institut") => `h.${Buffer.from(JSON.stringify({ sub: "manager", role })).toString("base64url")}.s`;
const reply = (v: unknown) => new Response(JSON.stringify(v), { headers: { "Content-Type": "application/json" } });
async function input(value: string) { await act(async () => {
  const el = document.querySelector("input")!; Object.getOwnPropertyDescriptor(dom.window.HTMLInputElement.prototype, "value")!.set!.call(el, value);
  el.dispatchEvent(new dom.window.Event("input", { bubbles: true })); el.dispatchEvent(new dom.window.Event("change", { bubbles: true }));
}); }
async function click() { await act(async () => document.querySelector("button")!.click()); }
test("manager explicitly reads capacity and source details, refuses malformed reread and discards late data", async () => {
  setAccessToken(token()); const root = createRoot(document.getElementById("root")!); let calls = 0, corrupt = false;
  globalThis.fetch = async () => { calls++; return reply(corrupt ? { ...report(), bookable_capacity: "0" } : report()); };
  try {
    await act(async () => root.render(<RevenueCapacityReport institute="inst" timezone={props.timezone} />));
    assert.equal(calls, 0); await click(); assert.equal(calls, 0);
    await input(props.day); await click(); assert.equal(calls, 1);
    assert.match(document.body.textContent!, /≈ 50,00 %/); assert.match(document.body.textContent!, /1 h 00 min 00,000001 s/);
    assert.match(document.body.textContent!, /Session session/); assert.match(document.body.textContent!, /Déclaration work/);
    corrupt = true; await click(); assert.ok(document.querySelector('[role="alert"]')); assert.doesNotMatch(document.body.textContent!, /50,00 %/);
    let resolve: (r: Response) => void = () => {}; globalThis.fetch = () => new Promise<Response>(r => { resolve = r; });
    await click(); await input("2025-10-25"); await act(async () => resolve(reply(report()))); assert.doesNotMatch(document.body.textContent!, /50,00 %/);
    await input(props.day); await click(); setAccessToken(token("accueil"));
    await act(async () => resolve(reply(report()))); assert.doesNotMatch(document.body.textContent!, /50,00 %/);
    setAccessToken(token()); await click();
    await act(async () => root.render(<RevenueCapacityReport institute="other" timezone={props.timezone} />));
    await act(async () => resolve(reply(report()))); assert.doesNotMatch(document.body.textContent!, /50,00 %/);
    setAccessToken(token("accueil")); await act(async () => root.render(<RevenueCapacityReport institute="inst" timezone={props.timezone} />));
    assert.equal(document.querySelector("button"), null);
  } finally { await act(async () => root.unmount()); }
});
