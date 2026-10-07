import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import React, { act } from "react";
import { RebookingPanel } from "../src/components/RebookingPanel";
import { setAccessToken } from "../src/api/session";
import { original } from "./rebooking-fixture";
const dom = new JSDOM("<!doctype html><div id='root'></div>", { url: "http://localhost:5173" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (role = "responsable_institut", actor = "manager") => `h.${Buffer.from(JSON.stringify({ role, sub: actor })).toString("base64url")}.s`;
const response = (v: unknown) => new Response(JSON.stringify(v), { headers: { "Content-Type": "application/json" } });
const props = { institute: "inst", timezone: "Europe/Zurich", employees: [{ id: "emp", institute_id: "inst", first_name: "Angela", status: "available", skills: [] }] };
const key = (actor = "manager") => `flowpilot.rebooking-request:${JSON.stringify(["inst", actor])}`;
const terms = () => { const o = original(); return { source_kind: o.source_kind, source_id: o.source_id, target_appointment_id: o.target_appointment_id, reason: o.reason, idempotency_key: o.idempotency_key }; };
const page = (rows: unknown[] = []) => ({ institute_id: "inst", employee_id: "emp", generated_at: "2026-10-07T12:00:00Z", page: { offset: 0, limit: 20, total: rows.length }, rows });
const resume = () => [...document.querySelectorAll<HTMLButtonElement>("button")].find(b => b.textContent === "Reprendre la demande de rebooking conservée")!;
test("native original recovery keeps the request across failed fresh reads without reposting", async () => {
  const fetch = globalThis.fetch, root = createRoot(document.getElementById("root")!); let reads = 0, posts = 0;
  globalThis.fetch = async (url, init) => {
    if (init?.method === "POST") { posts++; throw new Error("Unexpected repost"); }
    if (String(url).includes("/original/")) return response(original());
    if (String(url).includes("/rebookings?")) return response(++reads === 2 ? { ...page([original()]), employee_id: "foreign" } : page([original()]));
    throw new Error("Choice reads are not needed for original recovery");
  };
  try {
    sessionStorage.clear(); setAccessToken(token()); sessionStorage.setItem(key(), JSON.stringify({ employee_id: "emp", intent: { type: "create", terms: terms() } }));
    await act(async () => root.render(<RebookingPanel {...props} />));
    await act(async () => resume().click()); assert.equal(posts, 0); assert.notEqual(sessionStorage.getItem(key()), null); assert.match(document.body.textContent!, /avant de poursuivre/);
    await act(async () => resume().click()); assert.equal(posts, 0); assert.equal(sessionStorage.getItem(key()), null); assert.match(document.body.textContent!, /Rebooking déclaré/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = fetch; }
});
test("late prior-actor original absence cannot post or clear its protected request", async () => {
  const fetch = globalThis.fetch, root = createRoot(document.getElementById("root")!); let pending: (v: Response) => void = () => {}; let posts = 0;
  globalThis.fetch = async (url, init) => {
    if (init?.method === "POST") { posts++; return response(original()); }
    if (String(url).includes("/original/")) return new Promise(resolve => { pending = resolve; });
    return response(page());
  };
  try {
    sessionStorage.clear(); setAccessToken(token()); sessionStorage.setItem(key(), JSON.stringify({ employee_id: "emp", intent: { type: "create", terms: terms() } }));
    await act(async () => root.render(<RebookingPanel {...props} />)); await act(async () => resume().click());
    setAccessToken(token("responsable_institut", "new")); await act(async () => root.render(<RebookingPanel {...props} />));
    await act(async () => pending(response(null))); assert.equal(posts, 0); assert.notEqual(sessionStorage.getItem(key()), null);
    setAccessToken(token("accueil")); await act(async () => root.render(<RebookingPanel {...props} />)); assert.equal(document.querySelector("section"), null);
  } finally { await act(async () => root.unmount()); globalThis.fetch = fetch; }
});
test("cancellation recovery checks unchanged original captures and exact signed cancellation", async () => {
  const fetch = globalThis.fetch, root = createRoot(document.getElementById("root")!); const o = original();
  const cancellation = { id: "cancel", institute_id: "inst", rebooking_id: o.id, actor_id: "manager", reason: "Correction", idempotency_key: "cancel-key", created_at: "2026-10-07T13:00:00.000001Z" };
  let corrupt = true, posts = 0;
  globalThis.fetch = async (url, init) => {
    if (init?.method === "POST") { posts++; throw new Error("Unexpected repost"); }
    if (String(url).includes("/rebooking-cancellations/original/")) return response(cancellation);
    if (String(url).endsWith("/rebookings/original")) { const verified = { ...original(), cancellation }; if (corrupt) verified.booking_capture.current_start = "2026-10-08T12:00:00.000001Z"; return response(verified); }
    if (String(url).includes("/rebookings?")) return response(page([{ ...original(), cancellation }]));
    throw new Error("Choice reads are not needed for cancellation recovery");
  };
  try {
    sessionStorage.clear(); setAccessToken(token()); sessionStorage.setItem(key(), JSON.stringify({ employee_id: "emp", intent: { type: "cancel", original: o, terms: { reason: cancellation.reason, idempotency_key: cancellation.idempotency_key } } }));
    await act(async () => root.render(<RebookingPanel {...props} />)); await act(async () => resume().click());
    assert.equal(posts, 0); assert.notEqual(sessionStorage.getItem(key()), null); assert.match(document.body.textContent!, /à vérifier/);
    corrupt = false; await act(async () => resume().click()); assert.equal(sessionStorage.getItem(key()), null); assert.match(document.body.textContent!, /original conservé/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = fetch; }
});
