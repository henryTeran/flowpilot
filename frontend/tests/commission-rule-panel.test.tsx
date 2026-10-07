import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import React, { act } from "react";
import { CommissionRulePanel } from "../src/components/CommissionRulePanel";
import { setAccessToken } from "../src/api/session";
import { rule } from "./commission-fixture";
import type { CommissionRule, RuleIntent } from "../src/commission-utils";
const dom = new JSDOM("<!doctype html><div id='root'></div>", { url: "http://localhost:5173" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (actor = "manager", role = "responsable_institut") => `h.${Buffer.from(JSON.stringify({ role, sub: actor })).toString("base64url")}.s`;
const key = (actor = "manager") => `flowpilot.commission-rule-request:${JSON.stringify(["inst", actor])}`;
const reply = (v: unknown, status = 200) => new Response(JSON.stringify(v), { status, headers: { "Content-Type": "application/json" } });
const props = { institute: "inst", timezone: "UTC", employees: [{ id: "emp", institute_id: "inst", first_name: "Angela", skills: [], status: "available" }], services: [] };
const page = (rows: CommissionRule[] = []) => ({ institute_id: "inst", employee_id: "emp", generated_at: "2026-10-25T12:00:00Z", page: { offset: 0, limit: 20, total: rows.length }, rows });
const button = (label: string) => [...document.querySelectorAll<HTMLButtonElement>("button")].find(b => b.textContent === label)!;
const resume = () => button("Reprendre la demande de règle conservée");
const terms = () => { const { id, institute_id, actor_id, created_at, timezone, period_start, period_end, cancellation, ...terms } = rule(); return terms; };
function save(intent: RuleIntent = { type: "create", terms: terms() }) { sessionStorage.clear(); setAccessToken(token()); sessionStorage.setItem(key(), JSON.stringify(intent)); }
test("original rule recovery retains pinned timezone and preserves request across failed journal read", async () => {
  const fetch = globalThis.fetch, root = createRoot(document.getElementById("root")!); let reads = 0, posts = 0;
  save(); globalThis.fetch = async (url, init) => {
    if (init?.method === "POST") posts++;
    const custom = { ...rule(), id: "custom", category: "__proto__" };
    return reply(String(url).includes("/original/") ? rule() : ++reads === 2 ? { ...page(), employee_id: "foreign" } : page([rule(), custom]));
  };
  try {
    await act(async () => root.render(<CommissionRulePanel {...props} />)); await act(async () => resume().click());
    assert.equal(posts, 0); assert.ok(sessionStorage.getItem(key())); assert.match(document.body.textContent!, /Relisez les règles/);
    assert.equal(resume().disabled, true); assert.equal(button("Actualiser les règles").disabled, false);
    await act(async () => button("Actualiser les règles").click()); await act(async () => resume().click());
    assert.equal(posts, 0); assert.equal(sessionStorage.getItem(key()), null); assert.match(document.body.textContent!, /Règle de commission enregistrée/);
    assert.match(document.body.textContent!, /Europe\/Zurich/);
    assert.match(document.body.textContent!, /catégorie : __proto__/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = fetch; }
});
test("lost create response is recovered through the original key without a second POST", async () => {
  const fetch = globalThis.fetch, root = createRoot(document.getElementById("root")!); let stored = false, posts = 0;
  save(); globalThis.fetch = async (url, init) => {
    if (init?.method === "POST") { posts++; assert.ok(sessionStorage.getItem(key())); stored = true; throw new Error("Lost reply"); }
    return reply(String(url).includes("/original/") ? stored ? rule() : null : page());
  };
  try {
    await act(async () => root.render(<CommissionRulePanel {...props} />)); await act(async () => resume().click());
    assert.equal(posts, 1); assert.ok(sessionStorage.getItem(key())); assert.match(document.body.textContent!, /Lost reply/);
    await act(async () => resume().click()); assert.equal(posts, 1); assert.equal(sessionStorage.getItem(key()), null);
  } finally { await act(async () => root.unmount()); globalThis.fetch = fetch; }
});
test("forged original actor or changed pinned policy cannot clear or repost a saved rule", async () => {
  const fetch = globalThis.fetch, root = createRoot(document.getElementById("root")!); let calls = 0, posts = 0;
  save(); globalThis.fetch = async (url, init) => {
    if (init?.method === "POST") posts++;
    const r = rule(); if (String(url).includes("/original/")) { calls++; if (calls === 1) r.actor_id = "other"; if (calls === 3) r.rate_basis_points = 2000; return reply(r); }
    return reply(page());
  };
  try {
    await act(async () => root.render(<CommissionRulePanel {...props} />)); await act(async () => resume().click()); assert.ok(sessionStorage.getItem(key()));
    await act(async () => resume().click()); assert.ok(sessionStorage.getItem(key())); assert.equal(posts, 0);
    await act(async () => resume().click()); assert.equal(sessionStorage.getItem(key()), null);
  } finally { await act(async () => root.unmount()); globalThis.fetch = fetch; }
});
test("cancellation recovery verifies the original policy and exact signed cancellation clock", async () => {
  const fetch = globalThis.fetch, root = createRoot(document.getElementById("root")!); let corrupt = true, posts = 0;
  const cancellation = { id: "cancel", institute_id: "inst", rule_id: "rule", actor_id: "manager", reason: "Correction", idempotency_key: "cancel-key", created_at: "2026-10-25T12:00:00.000001Z" };
  save({ type: "cancel", original: rule(), terms: { reason: cancellation.reason, idempotency_key: cancellation.idempotency_key } });
  globalThis.fetch = async (url, init) => {
    if (init?.method === "POST") posts++;
    if (String(url).includes("/original/")) return reply(cancellation);
    const r = { ...rule(), cancellation: { ...cancellation } };
    if (String(url).endsWith("/commission-rules/rule")) { if (corrupt) r.cancellation.created_at = "2026-10-25T12:00:00.000002Z"; return reply(r); }
    return reply(page([r]));
  };
  try {
    await act(async () => root.render(<CommissionRulePanel {...props} />)); await act(async () => resume().click()); assert.ok(sessionStorage.getItem(key()));
    corrupt = false; await act(async () => resume().click()); assert.equal(posts, 0); assert.equal(sessionStorage.getItem(key()), null);
    assert.match(document.body.textContent!, /commissions déjà enregistrées conservées/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = fetch; }
});
test("native form requires explicit policy, submits exact basis points and can cancel a retained rule", async () => {
  const fetch = globalThis.fetch, root = createRoot(document.getElementById("root")!); let stored: CommissionRule | undefined, posts = 0;
  const cancelled = { id: "cancel", institute_id: "inst", rule_id: "rule", actor_id: "manager", created_at: "2026-10-25T12:00:00Z", reason: "", idempotency_key: "" };
  sessionStorage.clear(); setAccessToken(token());
  globalThis.fetch = async (url, init) => {
    const path = String(url);
    if (init?.method === "POST") {
      posts++; const payload = JSON.parse(String(init.body)); assert.ok(sessionStorage.getItem(key()));
      if (path.endsWith("/cancel")) { Object.assign(cancelled, payload); stored!.cancellation = { ...cancelled }; return reply(cancelled); }
      assert.equal(payload.rate_basis_points, 1025); assert.equal(payload.service_id, null); assert.equal(payload.basis, "closed_attributed_line_gross");
      assert.deepEqual(Object.keys(payload).sort(), Object.keys(terms()).sort()); stored = { ...rule(), ...payload }; return reply(stored);
    }
    if (path.includes("/commission-rule-cancellations/original/")) return reply(stored?.cancellation || null);
    if (path.includes("/original/")) return reply(stored || null);
    if (path.endsWith("/commission-rules/rule")) return reply(stored);
    return reply(page(stored ? [stored] : []));
  };
  const set = async (label: string, value: string) => act(async () => {
    const field = [...document.querySelectorAll("label")].find(l => l.firstChild?.textContent === label)!.querySelector<HTMLInputElement | HTMLSelectElement>("input, select")!;
    Object.getOwnPropertyDescriptor(field.tagName === "SELECT" ? dom.window.HTMLSelectElement.prototype : dom.window.HTMLInputElement.prototype, "value")!.set!.call(field, value);
    field.dispatchEvent(new dom.window.Event(field.tagName === "SELECT" ? "change" : "input", { bubbles: true }));
  });
  const submit = async (label: string) => act(async () => document.querySelector(`form[aria-label='${label}']`)!.dispatchEvent(new dom.window.Event("submit", { bubbles: true, cancelable: true })));
  try {
    await act(async () => root.render(<CommissionRulePanel {...props} />)); await set("Collaboratrice des commissions", "emp");
    await submit("Enregistrer une règle de commission"); assert.equal(posts, 0);
    await set("Intitulé de la règle", "Explicit native policy"); await set("Devise de la règle", "CHF"); await set("Catégorie de la règle", "care");
    await set("Prestations couvertes", "all"); await set("Taux de commission (%)", "10,25"); await set("Arrondi au cent", "half_even");
    await set("Premier jour inclus", "2026-10-25"); await set("Dernier jour inclus", "2026-10-25"); await set("Motif de la règle", "Native choice");
    await submit("Enregistrer une règle de commission"); assert.equal(posts, 1); assert.equal(sessionStorage.getItem(key()), null);
    await act(async () => button("Annuler cette règle").click()); await set("Motif d’annulation de la règle", "Correction native");
    await submit("Annuler la règle sélectionnée"); assert.equal(posts, 2); assert.equal(sessionStorage.getItem(key()), null);
    assert.equal(stored!.cancellation!.reason, "Correction native"); assert.equal(button("Annuler cette règle"), undefined);
  } finally { await act(async () => root.unmount()); globalThis.fetch = fetch; }
});
test("late old-actor absence cannot post; reception cannot read protected rule histories", async () => {
  const fetch = globalThis.fetch, root = createRoot(document.getElementById("root")!); let resolve!: (r: Response) => void, posts = 0, reads = 0;
  save(); globalThis.fetch = async (url, init) => { reads++; if (init?.method === "POST") posts++;
    return String(url).includes("/original/") ? new Promise(done => { resolve = done; }) : reply(page()); };
  try {
    await act(async () => root.render(<CommissionRulePanel {...props} />)); await act(async () => resume().click());
    setAccessToken(token("other")); await act(async () => root.render(<CommissionRulePanel {...props} />));
    await act(async () => resolve(reply(null))); assert.equal(posts, 0); assert.ok(sessionStorage.getItem(key())); assert.equal(sessionStorage.getItem(key("other")), null);
    setAccessToken(token("front", "accueil")); const before = reads; await act(async () => root.render(<CommissionRulePanel {...props} />));
    assert.equal(document.querySelector("section"), null); assert.equal(reads, before);
  } finally { await act(async () => root.unmount()); globalThis.fetch = fetch; }
});
