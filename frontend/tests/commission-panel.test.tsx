import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import React, { act } from "react";
import { CommissionPanel } from "../src/components/CommissionPanel";
import { CommissionChoices } from "../src/components/CommissionChoices";
import { setAccessToken } from "../src/api/session";
import { original, rule, props as scope } from "./commission-fixture";
import { options } from "./commission-options-fixture";
const dom = new JSDOM("<!doctype html><div id='root'></div>", { url: "http://localhost:5173" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (actor = "manager", role = "responsable_institut") => `h.${Buffer.from(JSON.stringify({ role, sub: actor })).toString("base64url")}.s`;
const key = (actor = "manager") => `flowpilot.commission-request:${JSON.stringify(["inst", actor])}`;
const reply = (v: unknown) => new Response(JSON.stringify(v), { headers: { "Content-Type": "application/json" } });
const props = { institute: "inst", timezone: "UTC", employees: [{ id: "emp", institute_id: "inst", first_name: "Angela", skills: [], status: "available" }], services: [] };
const page = (rows: unknown[] = []) => ({ institute_id: "inst", employee_id: "emp", generated_at: "2026-10-25T12:00:00Z", page: { offset: 0, limit: 20, total: rows.length }, rows });
const button = (label: string) => [...document.querySelectorAll<HTMLButtonElement>("button")].find(b => b.textContent === label)!;
const resume = () => button("Reprendre la demande de commission conservée");
const terms = () => { const o = original(); return { rule_id: o.rule_id, line_id: o.line_id, reason: o.reason, idempotency_key: o.idempotency_key }; };
function save() { sessionStorage.clear(); setAccessToken(token()); sessionStorage.setItem(key(), JSON.stringify({ employee_id: "emp", intent: { type: "create", terms: terms() } })); }
test("lost commission reply recovers committed original without repost and retains request after failed history", async () => {
  const fetch = globalThis.fetch, root = createRoot(document.getElementById("root")!); let stored = false, posts = 0, journal = 0, corrupt = true;
  save(); globalThis.fetch = async (url, init) => {
    if (init?.method === "POST") { assert.ok(sessionStorage.getItem(key())); posts++; stored = true; throw new Error("Lost reply"); }
    const path = String(url); if (path.includes("/original/")) return reply(stored ? original() : null);
    if (path.endsWith("/commission-rules/rule")) return reply(rule());
    if (path.includes("/commission-rules?")) return reply(page([rule()]));
    journal++; return reply(corrupt && journal === 2 ? { ...page(), employee_id: "foreign" } : page(stored ? [original()] : []));
  };
  try {
    await act(async () => root.render(<CommissionPanel {...props} />)); await act(async () => resume().click()); assert.equal(posts, 1); assert.ok(sessionStorage.getItem(key()));
    await act(async () => resume().click()); assert.equal(posts, 1); assert.ok(sessionStorage.getItem(key())); assert.equal(resume().disabled, true);
    corrupt = false; await act(async () => button("Actualiser le journal des commissions").click()); await act(async () => resume().click());
    assert.equal(posts, 1); assert.equal(sessionStorage.getItem(key()), null); assert.match(document.body.textContent!, /Commission enregistrée/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = fetch; }
});
test("commission cancellation recovery rejects changed pinned source or signed microsecond", async () => {
  const fetch = globalThis.fetch, root = createRoot(document.getElementById("root")!); let corrupt = "clock", posts = 0;
  const cancellation = { id: "cancel", institute_id: "inst", commission_id: "commission", actor_id: "manager", reason: "Correction", idempotency_key: "cancel-key", created_at: "2026-10-25T12:00:00.000002Z" };
  save(); sessionStorage.setItem(key(), JSON.stringify({ employee_id: "emp", intent: { type: "cancel", original: original(), terms: { reason: cancellation.reason, idempotency_key: cancellation.idempotency_key } } }));
  globalThis.fetch = async (url, init) => {
    if (init?.method === "POST") posts++;
    const path = String(url); if (path.includes("/original/")) return reply(cancellation);
    const o = { ...original(), cancellation: { ...cancellation } };
    if (path.endsWith("/commissions/commission")) { if (corrupt === "clock") o.cancellation.created_at = "2026-10-25T12:00:00.000003Z";
      if (corrupt === "source") o.calculation.source.arrival_at = "2026-10-25T09:00:00.000001Z"; return reply(o); }
    return reply(page(path.includes("/commission-rules?") ? [rule()] : [o]));
  };
  try {
    await act(async () => root.render(<CommissionPanel {...props} />)); await act(async () => resume().click()); assert.ok(sessionStorage.getItem(key()));
    corrupt = "source"; await act(async () => resume().click()); assert.ok(sessionStorage.getItem(key()));
    corrupt = ""; await act(async () => resume().click()); assert.equal(posts, 0); assert.equal(sessionStorage.getItem(key()), null); assert.match(document.body.textContent!, /original conservé/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = fetch; }
});
test("late old actor original absence cannot post or clear its commission request; reception cannot read", async () => {
  const fetch = globalThis.fetch, root = createRoot(document.getElementById("root")!); let resolve!: (r: Response) => void, posts = 0, reads = 0;
  save(); globalThis.fetch = async (url, init) => { reads++; if (init?.method === "POST") posts++;
    return String(url).includes("/original/") ? new Promise(done => { resolve = done; }) : reply(page()); };
  try {
    await act(async () => root.render(<CommissionPanel {...props} />)); await act(async () => resume().click());
    setAccessToken(token("other")); await act(async () => root.render(<CommissionPanel {...props} />)); await act(async () => resolve(reply(null)));
    assert.equal(posts, 0); assert.ok(sessionStorage.getItem(key())); assert.equal(sessionStorage.getItem(key("other")), null);
    setAccessToken(token("front", "accueil")); const before = reads; await act(async () => root.render(<CommissionPanel {...props} />)); assert.equal(reads, before); assert.equal(document.querySelector("section"), null);
  } finally { await act(async () => root.unmount()); globalThis.fetch = fetch; }
});
test("a saved request cannot newly post a rule belonging to another employee", async () => {
  const fetch = globalThis.fetch, root = createRoot(document.getElementById("root")!); let posts = 0;
  save(); globalThis.fetch = async (url, init) => {
    if (init?.method === "POST") posts++;
    const path = String(url); if (path.includes("/original/")) return reply(null);
    if (path.endsWith("/commission-rules/rule")) return reply({ ...rule(), employee_id: "other" });
    return reply(page());
  };
  try {
    await act(async () => root.render(<CommissionPanel {...props} />)); await act(async () => resume().click());
    assert.equal(posts, 0); assert.ok(sessionStorage.getItem(key())); assert.match(document.body.textContent!, /Périmètre original/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = fetch; }
});
test("source choice verifies exact preview and clears selection on refresh, scope change and exclusions", async () => {
  const fetch = globalThis.fetch, root = createRoot(document.getElementById("root")!); let corrupt = false, excluded = false, selected: unknown;
  globalThis.fetch = async () => { const r = options(); if (corrupt) r.rows[0].calculation!.amount_minor = "105";
    if (excluded) { r.rows[0].already_attributed = true; r.rows[0].exclusion = "already_attributed"; r.rows[0].calculation = null; } return reply(r); };
  const change = async () => act(async () => { const select = document.querySelector("select")!; select.value = "line"; select.dispatchEvent(new dom.window.Event("change", { bubbles: true })); });
  const attributes = { ...scope, rule: rule(), services: [], onSelection: (v: unknown) => { selected = v; } };
  try {
    setAccessToken(token()); await act(async () => root.render(<CommissionChoices {...attributes} />)); await change(); assert.ok(selected); assert.match(document.body.textContent!, /1,04 CHF/);
    corrupt = true; await act(async () => button("Actualiser les sources de commission").click()); assert.equal(selected, undefined); assert.equal(document.querySelector("select"), null); assert.match(document.body.textContent!, /à vérifier/);
    corrupt = false; await act(async () => button("Actualiser les sources de commission").click()); await change();
    excluded = true; await act(async () => button("Actualiser les sources de commission").click());
    assert.equal(document.querySelector<HTMLOptionElement>("option[value='line']")!.disabled, true); await change(); assert.equal(selected, undefined);
    await act(async () => root.render(<CommissionChoices {...attributes} disabled />)); assert.equal(selected, undefined); assert.equal(document.querySelector("details"), null);
  } finally { await act(async () => root.unmount()); globalThis.fetch = fetch; }
});
