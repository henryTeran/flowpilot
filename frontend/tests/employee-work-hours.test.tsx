import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import React, { act } from "react";
import { EmployeeWorkHoursPanel } from "../src/components/EmployeeWorkHoursPanel";
import { setAccessToken } from "../src/api/session";
const dom = new JSDOM("<!doctype html><div id='root'></div>", { url: "http://localhost:5173" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (role = "responsable_institut", actor = "manager") => `h.${Buffer.from(JSON.stringify({ role, sub: actor })).toString("base64url")}.s`;
const props = { institute: "inst", employee: "emp", day: "2025-10-26", start: "2025-10-25T22:00:00Z", end: "2025-10-26T23:00:00Z", timezone: "Europe/Zurich" };
const reply = (employee: string) => new Response(JSON.stringify({ institute_id: "inst", employee_id: employee, day: props.day, timezone: props.timezone,
  start: props.start, end: props.end, generated_at: "2026-10-07T12:00:00Z", page: { offset: 0, limit: 20, total: 0 }, rows: [], active_sources: 0,
  future_end_sources: 0, overlap_sources: 0, known_declared_duration_us: "0", known_union_duration_us: "0", recorded_duration_us: null, complete_attendance: false }), { headers: { "Content-Type": "application/json" } });
test("native hours deny reception reads, isolate late old scope and hide a failed fresh read", async () => {
  const fetch = globalThis.fetch, root = createRoot(document.getElementById("root")!), pending: ((v: Response) => void)[] = [];
  globalThis.fetch = async () => new Promise(resolve => pending.push(resolve));
  try {
    setAccessToken(token("accueil")); await act(async () => root.render(<EmployeeWorkHoursPanel {...props} />)); assert.equal(pending.length, 0);
    setAccessToken(token()); await act(async () => root.render(<EmployeeWorkHoursPanel {...props} />));
    await act(async () => root.render(<EmployeeWorkHoursPanel {...props} employee="other" />));
    await act(async () => pending[0](reply("emp"))); assert.doesNotMatch(document.body.textContent!, /Total enregistré/);
    setAccessToken(token("responsable_institut", "new")); await act(async () => root.render(<EmployeeWorkHoursPanel {...props} employee="other" />));
    await act(async () => pending[1](reply("other"))); assert.doesNotMatch(document.body.textContent!, /Total enregistré/);
    await act(async () => pending[2](reply("other"))); assert.match(document.body.textContent!, /heures travaillées restent inconnues/);
    await act(async () => document.querySelector<HTMLButtonElement>("button")!.click()); assert.doesNotMatch(document.body.textContent!, /Total enregistré/);
    await act(async () => pending[3](reply("foreign"))); assert.match(document.body.textContent!, /à vérifier/); assert.doesNotMatch(document.body.textContent!, /Total enregistré/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = fetch; }
});
