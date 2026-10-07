import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import React, { act } from "react";
import { ObjectivePanel } from "../src/components/ObjectivePanel";
import { setAccessToken } from "../src/api/session";
import type { Objective, ObjectiveIntent } from "../src/objective-utils";
const dom = new JSDOM("<!doctype html><div id='root'></div>", { url: "http://localhost:5173" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (actor: string) => `h.${Buffer.from(JSON.stringify({ role: "responsable_institut", sub: actor })).toString("base64url")}.s`;
const key = (actor: string) => `flowpilot.objective-request:${JSON.stringify(["inst", actor])}`;
const terms = { employee_id: "emp", title: "Original", metric: "closed_attributed_gross" as const, currency: "CHF" as const,
  target: "90071992547409.93", first_day: "2026-10-25", last_day: "2026-10-25", reason: "Declared", idempotency_key: "key" };
const original: Objective = { ...terms, id: "obj", institute_id: "inst", actor_id: "manager", timezone: "Europe/Zurich",
  period_start: "2026-10-24T22:00:00Z", period_end: "2026-10-25T23:00:00Z", created_at: "2026-10-07T12:00:00Z", cancellation: null };
const reply = (value: unknown) => new Response(JSON.stringify(value), { headers: { "Content-Type": "application/json" } });
const page = { institute_id: "inst", employee_id: "emp", generated_at: "2026-10-07T12:00:00Z", page: { offset: 0, limit: 20, total: 0 }, rows: [] };
const props = { institute: "inst", timezone: "UTC", employees: [{ id: "emp", institute_id: "inst", first_name: "Angela", skills: [], status: "available" }] };
const resume = () => [...document.querySelectorAll<HTMLButtonElement>("button")].find(b => b.textContent === "Reprendre la demande d’objectif conservée")!;
test("saved objective recovers pinned original despite current timezone change and preserves request after failed fresh read", async () => {
  const fetch = globalThis.fetch, root = createRoot(document.getElementById("root")!); let corrupt = true, posts = 0, originals = 0;
  sessionStorage.clear(); setAccessToken(token("manager")); const intent: ObjectiveIntent = { type: "create", terms };
  sessionStorage.setItem(key("manager"), JSON.stringify(intent));
  globalThis.fetch = async (url, options) => {
    if (options?.method === "POST") { posts++; return reply(original); }
    if (String(url).includes("/original/")) { originals++; return reply(original); }
    return reply(corrupt && originals > 0 ? { ...page, employee_id: "foreign" } : page);
  };
  try {
    await act(async () => root.render(<ObjectivePanel {...props} />)); await act(async () => resume().click());
    assert.equal(posts, 0); assert.ok(sessionStorage.getItem(key("manager"))); assert.match(document.body.textContent!, /Actualisez les objectifs/);
    corrupt = false; await act(async () => resume().click()); assert.equal(posts, 0); assert.equal(originals, 4);
    assert.equal(sessionStorage.getItem(key("manager")), null); assert.match(document.body.textContent!, /Objectif enregistré/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = fetch; }
});
test("late old-actor original absence cannot POST or clear the old request", async () => {
  const fetch = globalThis.fetch, root = createRoot(document.getElementById("root")!); let resolve!: (v: Response) => void, posts = 0;
  sessionStorage.clear(); setAccessToken(token("manager")); sessionStorage.setItem(key("manager"), JSON.stringify({ type: "create", terms }));
  globalThis.fetch = async (url, options) => { if (options?.method === "POST") posts++;
    return String(url).includes("/original/") ? new Promise(done => { resolve = done; }) : reply(page); };
  try {
    await act(async () => root.render(<ObjectivePanel {...props} />)); await act(async () => resume().click());
    setAccessToken(token("other")); await act(async () => root.render(<ObjectivePanel {...props} />));
    await act(async () => resolve(reply(null))); assert.equal(posts, 0); assert.ok(sessionStorage.getItem(key("manager")));
    assert.equal(sessionStorage.getItem(key("other")), null); assert.doesNotMatch(document.body.textContent!, /Demande d’objectif conservée/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = fetch; }
});
