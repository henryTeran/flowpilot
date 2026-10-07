import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import React, { act } from "react";
import { EmployeeCalendarPanel } from "../src/components/EmployeeCalendarPanel";
import { validEmployeeDay, type EmployeeDay } from "../src/employee-calendar-utils";
import { setAccessToken } from "../src/api/session";
const dom = new JSDOM("<!doctype html><div id='root'></div>", { url: "http://localhost:5173" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (role = "responsable_institut", sub = "manager") => `h.${Buffer.from(JSON.stringify({ role, sub })).toString("base64url")}.s`;
const response = (value: unknown) => new Response(JSON.stringify(value), { headers: { "Content-Type": "application/json" } });
function snapshot(day = "2026-10-25"): EmployeeDay {
  return { institute_id: "inst", generated_at: "2026-10-07T12:00:00Z", employee: { id: "emp", first_name: "Angela", status: "available", skills: ["CARE"] }, day,
    timezone: "Europe/Zurich", day_start: "2026-10-24T22:00:00Z", day_end: "2026-10-25T23:00:00Z",
    availability: { employee_id: "emp", institute_id: "inst", service_id: null, available: true, current_slot: { employee_id: "emp", institute_id: "inst", available_from: "2026-10-07T12:00:00Z", available_until: null, reason: "available_now" }, upcoming_slots: [] },
    event_page: { offset: 0, limit: 50, total: 1 }, events: [{ source_kind: "absence", id: "abs", status: "cancelled", service_id: null, service_name: null,
      start_time: "2026-10-25T00:30:00Z", end_time: "2026-10-25T01:30:00Z", actual_start_time: null, actual_end_time: null, absence_kind: "leave", reason: "Original leave", cancellation_id: "cancel" }] };
}
test("individual calendar rejects foreign scope, missing pages, forged execution and contradictory availability", () => {
  assert.equal(validEmployeeDay(snapshot(), "inst", "emp", "2026-10-25", 0), true);
  const skipped = { ...snapshot("2011-12-30"), timezone: "Pacific/Apia", day_start: "2011-12-30T10:00:00Z", day_end: "2011-12-30T10:00:00Z", events: [], event_page: { offset: 0, limit: 50, total: 0 } };
  assert.equal(validEmployeeDay(skipped, "inst", "emp", "2011-12-30", 0), true);
  assert.equal(validEmployeeDay({ ...skipped, day: "2011-12-29", day_start: "2011-12-29T10:00:00Z" }, "inst", "emp", "2011-12-29", 0), true);
  for (const corrupt of [
    (row: EmployeeDay) => { row.employee.id = "foreign"; }, (row: EmployeeDay) => { row.availability.institute_id = "foreign"; },
    (row: EmployeeDay) => { row.event_page.total = 2; }, (row: EmployeeDay) => { row.events[0].actual_end_time = "2026-10-25T01:30:00Z"; },
    (row: EmployeeDay) => { row.events[0].cancellation_id = null; }, (row: EmployeeDay) => { row.availability.current_slot!.available_from = "2026-10-25T00:00:00Z"; },
    (row: EmployeeDay) => { row.day_start = "2026-10-25T00:00:00"; }, (row: EmployeeDay) => { row.timezone = "Unknown/Clock"; },
    (row: EmployeeDay) => { row.day_start = "2026-10-23T22:00:00Z"; },
    (row: EmployeeDay) => { row.day_start = "2026-10-24T23:00:00Z"; },
    (row: EmployeeDay) => { row.availability.upcoming_slots = [null as never]; },
    (row: EmployeeDay) => { row.events[0].start_time = "2026-10-26T00:00:00Z"; row.events[0].end_time = "2026-10-26T01:00:00Z"; },
  ]) { const row = snapshot(); corrupt(row); assert.equal(validEmployeeDay(row, "inst", "emp", "2026-10-25", 0), false); }
});

test("native calendar refuses reception reads, hides failed facts and isolates late old employee/session responses", async () => {
  const originalFetch = globalThis.fetch, root = createRoot(document.getElementById("root")!);
  const pending: { day: string; resolve: (value: Response) => void }[] = [];
  globalThis.fetch = async url => String(url).includes("/certifications?") ? response({ institute_id: "inst", employee_id: "emp",
    generated_at: "2026-10-07T12:00:00Z", page: { offset: 0, limit: 50, total: 0 }, rows: [] })
    : String(url).includes("/occupation?") ? response({ work_hours: { institute_id: "inst", employee_id: "emp", day: new URL(String(url)).searchParams.get("day"), timezone: "Europe/Zurich", start: snapshot().day_start, end: snapshot().day_end, generated_at: "2026-10-07T12:00:00Z", page: { offset: 0, limit: 20, total: 0 }, rows: [], active_sources: 0, future_end_sources: 0, overlap_sources: 0, known_declared_duration_us: "0", known_union_duration_us: "0", recorded_duration_us: null, complete_attendance: false }, page: { offset: 0, limit: 20, total: 0 }, rows: [], diagnostics: { retained: 0, missing_start: 0, missing_end: 0, invalid_interval: 0, future_end: 0, unfinalized: 0 }, known_busy_duration_us: "0", covered_busy_duration_us: "0", outside_recorded_work_duration_us: "0", recorded_occupation_basis_points: null, complete_activity: false })
    : String(url).includes("/work-hours?") ? response({ institute_id: "inst", employee_id: "emp", day: new URL(String(url)).searchParams.get("day"), timezone: "Europe/Zurich", start: snapshot().day_start, end: snapshot().day_end, generated_at: "2026-10-07T12:00:00Z", page: { offset: 0, limit: 20, total: 0 }, rows: [], active_sources: 0, future_end_sources: 0, overlap_sources: 0, known_declared_duration_us: "0", known_union_duration_us: "0", recorded_duration_us: null, complete_attendance: false })
    : String(url).includes("/objectives?") ? response({ institute_id: "inst", employee_id: "emp", generated_at: "2026-10-07T12:00:00Z", page: { offset: 0, limit: 20, total: 0 }, rows: [] })
    : String(url).includes("/revenue?") ? response({ institute_id: "inst", employee_id: "emp", day: new URL(String(url)).searchParams.get("day"), start: snapshot().day_start, end: snapshot().day_end, generated_at: "2026-10-07T12:00:00Z", page: { offset: 0, limit: 50, total: 0 }, rows: [], currencies: [], institute_unattributed_lines: 0 })
    : new Promise(resolve => pending.push({ day: new URL(String(url)).searchParams.get("day")!, resolve }));
  const employees = [{ id: "emp", institute_id: "inst", first_name: "Angela", skills: [], status: "available" }];
  const render = () => <EmployeeCalendarPanel institute="inst" employees={employees} timezone="Europe/Zurich" />;
  try {
    sessionStorage.clear(); setAccessToken(token("accueil")); await act(async () => root.render(render())); assert.equal(pending.length, 0);
    setAccessToken(token()); await act(async () => root.render(render()));
    await act(async () => { const date = document.querySelector("input")!;
      Object.getOwnPropertyDescriptor(dom.window.HTMLInputElement.prototype, "value")!.set!.call(date, "2026-10-25");
      date.dispatchEvent(new dom.window.Event("input", { bubbles: true })); });
    const choose = async () => act(async () => { const select = document.querySelector("select")!; select.value = "emp"; select.dispatchEvent(new dom.window.Event("change", { bubbles: true })); });
    await choose(); assert.equal(pending.length, 1);
    await act(async () => pending[0].resolve(response(snapshot(pending[0].day))));
    assert.match(document.body.textContent!, /25 heures réelles/); assert.match(document.body.textContent!, /UTC\+02:00.*UTC\+01:00/s);
    const button = [...document.querySelectorAll<HTMLButtonElement>("button")].find(item => item.textContent === "Actualiser le calendrier individuel")!;
    await act(async () => button.click()); assert.equal(document.querySelector(".absence-list"), null);
    await act(async () => pending[1].resolve(response({ ...snapshot(pending[1].day), institute_id: "foreign" })));
    assert.match(document.body.textContent!, /Lecture du calendrier à vérifier/);
    await act(async () => button.click()); setAccessToken(token("responsable_institut", "new-manager")); await act(async () => root.render(render()));
    await act(async () => pending[2].resolve(response(snapshot(pending[2].day)))); assert.equal(document.querySelector(".absence-list"), null);
  } finally { await act(async () => root.unmount()); globalThis.fetch = originalFetch; }
});
