import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import React, { act } from "react";
import { WorkIntervalPanel } from "../src/components/WorkIntervalPanel";
import { setAccessToken } from "../src/api/session";
import { sameWorkOriginal, validWorkIntent, type WorkInterval } from "../src/work-hours-utils";
const dom = new JSDOM("<!doctype html><div id='root'></div>", { url: "http://localhost:5173" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (actor: string) => `h.${Buffer.from(JSON.stringify({ role: "responsable_institut", sub: actor })).toString("base64url")}.s`;
const key = (actor: string) => `flowpilot.work-request:${JSON.stringify(["inst", actor])}`;
const original: WorkInterval = { id: "wrk", institute_id: "inst", employee_id: "emp", actor_id: "manager", created_at: "2026-10-07T00:00:00Z", start_time: "2025-10-26T00:30:00.000001Z", end_time: "2025-10-26T01:30:00.000002Z", reason: "Declared", idempotency_key: "key", cancellation: null };
const terms = { employee_id: original.employee_id, start_time: original.start_time, end_time: original.end_time, reason: original.reason, idempotency_key: original.idempotency_key };
const reply = (v: unknown) => new Response(JSON.stringify(v), { headers: { "Content-Type": "application/json" } });
const page = { institute_id: "inst", employee_id: "emp", generated_at: "2026-10-07T12:00:00Z", page: { offset: 0, limit: 20, total: 1 }, rows: [original] };
const props = { institute: "inst", timezone: "UTC", employees: [{ id: "emp", institute_id: "inst", first_name: "Angela", skills: [], status: "available" }] };
const resume = () => [...document.querySelectorAll<HTMLButtonElement>("button")].find(b => b.textContent === "Reprendre la demande d’heures conservée")!;
test("hour recovery retains microsecond originals after a failed fresh page and never reposts", async () => {
  const fetch = globalThis.fetch, root = createRoot(document.getElementById("root")!); let reads = 0, posts = 0, corrupt = true;
  sessionStorage.clear(); setAccessToken(token("manager")); sessionStorage.setItem(key("manager"), JSON.stringify({ type: "create", terms }));
  globalThis.fetch = async (url, options) => {
    if (options?.method === "POST") posts++;
    if (String(url).includes("/original/")) { reads++; return reply(original); }
    return reply(corrupt && reads > 0 ? { ...page, employee_id: "foreign" } : page);
  };
  try {
    await act(async () => root.render(<WorkIntervalPanel {...props} />)); await act(async () => resume().click());
    assert.equal(posts, 0); assert.ok(sessionStorage.getItem(key("manager"))); assert.match(document.body.textContent!, /Actualisez les heures originales/);
    corrupt = false; await act(async () => resume().click()); assert.equal(posts, 0); assert.equal(reads, 4);
    assert.equal(sessionStorage.getItem(key("manager")), null); assert.match(document.body.textContent!, /Heures effectives enregistrées/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = fetch; }
});
test("late old actor cannot post an absent hour original or clear protected storage", async () => {
  const fetch = globalThis.fetch, root = createRoot(document.getElementById("root")!); let resolve!: (v: Response) => void, posts = 0;
  sessionStorage.clear(); setAccessToken(token("manager")); sessionStorage.setItem(key("manager"), JSON.stringify({ type: "create", terms }));
  globalThis.fetch = async (url, options) => { if (options?.method === "POST") posts++;
    return String(url).includes("/original/") ? new Promise(done => { resolve = done; }) : reply(page); };
  try {
    await act(async () => root.render(<WorkIntervalPanel {...props} />)); await act(async () => resume().click());
    setAccessToken(token("other")); await act(async () => root.render(<WorkIntervalPanel {...props} />));
    await act(async () => resolve(reply(null))); assert.equal(posts, 0); assert.ok(sessionStorage.getItem(key("manager")));
    assert.equal(sessionStorage.getItem(key("other")), null); assert.doesNotMatch(document.body.textContent!, /Demande d’heures conservée/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = fetch; }
});
test("cancellation guards keep exact owned interval terms and immutable microseconds", () => {
  assert.equal(validWorkIntent({ type: "cancel", original, terms: { reason: "Revised", idempotency_key: "cancel" } }, "inst"), true);
  assert.equal(validWorkIntent({ type: "cancel", original: { ...original, institute_id: "foreign" }, terms }, "inst"), false);
  assert.equal(sameWorkOriginal(original, { ...original, end_time: "2025-10-26T01:30:00.000003Z" }), false);
  assert.equal(sameWorkOriginal(original, { ...original, actor_id: "other" }), false);
});
test("timezone changes isolate a pending civil-clock scope while preserving the original UTC request", async () => {
  const fetch = globalThis.fetch, root = createRoot(document.getElementById("root")!); let resolve!: (v: Response) => void, posts = 0;
  sessionStorage.clear(); setAccessToken(token("manager")); const saved = JSON.stringify({ type: "create", terms }); sessionStorage.setItem(key("manager"), saved);
  globalThis.fetch = async (url, options) => { if (options?.method === "POST") posts++;
    return String(url).includes("/original/") ? new Promise(done => { resolve = done; }) : reply(page); };
  try {
    await act(async () => root.render(<WorkIntervalPanel {...props} />)); await act(async () => resume().click());
    await act(async () => root.render(<WorkIntervalPanel {...props} timezone="Europe/Zurich" />));
    await act(async () => resolve(reply(null))); assert.equal(posts, 0); assert.equal(sessionStorage.getItem(key("manager")), saved);
    assert.match(document.body.textContent!, /Demande d’heures conservée/); assert.match(document.body.textContent!, /2025-10-26T00:30:00.000001Z/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = fetch; }
});
