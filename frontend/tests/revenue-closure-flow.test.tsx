import test from "node:test";
import assert from "node:assert/strict";
import React, { act } from "react";
import { JSDOM } from "jsdom";
import { readFileSync } from "node:fs";
import { RevenueBookingClosures } from "../src/components/RevenueBookingClosures";
import { RevenueClosureWriter } from "../src/components/RevenueClosureWriter";
import { setAccessToken } from "../src/api/session";
import { revenueOriginalFingerprint } from "../src/revenue-scenario-utils";
const vector = JSON.parse(readFileSync(new URL("./fixtures/revenue-closure-14s.json", import.meta.url), "utf8"));
const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (role = "responsable_institut") => `h.${Buffer.from(JSON.stringify({ sub: "manager", role })).toString("base64url")}.s`;
const storage = 'flowpilot.closure-valuation.v1:["own","manager"]';
const reply = (v: unknown, status = 200) => new Response(JSON.stringify(v), { status, headers: { "Content-Type": "application/json" } });
const button = (text: string) => Array.from(document.querySelectorAll("button")).find(b => b.textContent!.includes(text))!;
async function settle() { for (let n = 0; n < 250 && document.querySelector('[role="status"]'); n++) await act(async () => { await new Promise(r => setTimeout(r, 20)); }); assert.equal(document.querySelector('[role="status"]'), null); }
async function click(text: string) { await act(async () => button(text).click()); await settle(); }
async function input(element: HTMLInputElement | HTMLTextAreaElement, value: string) { await act(async () => {
  const prototype = element instanceof dom.window.HTMLTextAreaElement ? dom.window.HTMLTextAreaElement.prototype : dom.window.HTMLInputElement.prototype;
  Object.getOwnPropertyDescriptor(prototype, "value")!.set!.call(element, value); element.dispatchEvent(new dom.window.Event("input", { bubbles: true })); element.dispatchEvent(new dom.window.Event("change", { bubbles: true }));
}); }
async function terms() { await act(async () => { const s = document.querySelector("select")!; s.value = "member"; s.dispatchEvent(new dom.window.Event("change", { bubbles: true })); }); await input(document.querySelector("textarea")!, "Motif 😀\nDécision explicite"); }
const props = { institute: "own", closure: vector.closure_report.opportunities[0].evidence, reference: vector.references.originals[0] };
async function envelope(body: any) { const e = structuredClone(vector.original); e.original.request = body.valuation; e.original.idempotency_key = body.idempotency_key; e.fingerprint = await revenueOriginalFingerprint(e.original); return e; }
test("explicit source/reference review retains lost-ack request across reload and independently recovers without second POST", async () => {
  sessionStorage.clear(); setAccessToken(token()); let root = createRoot(document.getElementById("root")!), posts = 0, reads = 0, retained: any = null, bad = false;
  globalThis.fetch = async (url, init) => {
    if (init?.method === "POST") { posts++; const body = JSON.parse(init.body as string); assert.deepEqual(JSON.parse(sessionStorage.getItem(storage)!).terms, body); retained = await envelope(body); throw new TypeError("lost acknowledgement"); }
    reads++;
    if (String(url).includes("/booking-closures?")) return reply(bad ? { ...vector.closure_report, cancelled_revenue: "0" } : vector.closure_report);
    if (String(url).includes("/price-references?")) return reply(vector.references);
    if (String(url).includes("/closure-value-originals?")) return reply({ institute_id: "own", captured_at: vector.references.captured_at, offset: 0, limit: 20, total: 1, originals: [retained], full_original_cohort_verified: true, causal_loss_proven: false, action_executed: false });
    return reply(retained);
  };
  try {
    await act(async () => root.render(<RevenueBookingClosures institute="own" timezone="UTC" />)); assert.equal(reads, 0); assert.equal(posts, 0);
    const dates = document.querySelectorAll<HTMLInputElement>('input[type="date"]'); await input(dates[0], "2026-01-01"); await input(dates[1], "2026-01-03");
    await click("Lire les événements terminaux"); assert.equal(reads, 1); assert.match(document.body.textContent!, /Absence déclarée/);
    await click("Lire les références tarifaires"); assert.equal(reads, 2); assert.match(document.body.textContent!, /9\.87 CHF/);
    await click("Choisir cette référence"); await terms(); await click("Conserver ce scénario"); assert.equal(posts, 1); assert.ok(sessionStorage.getItem(storage));
    await act(async () => root.unmount()); root = createRoot(document.getElementById("root")!); const before = reads;
    await act(async () => root.render(<RevenueBookingClosures institute="own" timezone="UTC" />)); assert.equal(reads, before);
    await click("Reprendre la valorisation"); assert.equal(posts, 1); assert.equal(reads, before+3); assert.equal(sessionStorage.getItem(storage), null);
    assert.match(document.body.textContent!, /Valorisation conservée et relue/); await click("Lire les valorisations conservées"); assert.match(document.querySelector('[aria-label="Valorisations conservées"]')!.textContent!, /9\.87 CHF/);
    await click("Déclarer une autre valorisation"); assert.equal(document.querySelector("select")!.value, ""); assert.equal(document.querySelector("textarea")!.value, "");
    await input(document.querySelectorAll<HTMLInputElement>('input[type="date"]')[0], "2026-01-01"); await input(document.querySelectorAll<HTMLInputElement>('input[type="date"]')[1], "2026-01-03");
    bad = true; await click("Lire les événements terminaux"); assert.ok(document.querySelector('[role="alert"]')); assert.equal(document.querySelector('[aria-label="Références tarifaires de la réservation"]'), null);
  } finally { await act(async () => root.unmount()); sessionStorage.clear(); }
});
test("changed independent receipt refuses acknowledgement, definitive rejection verifies absent key before correction", async () => {
  for (const mode of ["actor", "id-read", "rejection"]) {
    sessionStorage.clear(); setAccessToken(token()); const root = createRoot(document.getElementById("root")!); let retained: any = null, callbacks = 0, reads = 0;
    globalThis.fetch = async (url, init) => {
      if (init?.method === "POST") { if (mode === "rejection") return reply({ detail: "invalid" }, 422); retained = await envelope(JSON.parse(init.body as string)); return reply(retained); }
      reads++; if (!retained) return reply(null); const e = structuredClone(retained);
      if (mode === "actor") e.original.actor_id = "other";
      if (mode === "id-read" && String(url).includes("/closure-value-originals/")) e.original.id = "substituted";
      e.fingerprint = await revenueOriginalFingerprint(e.original); return reply(e);
    };
    try {
      await act(async () => root.render(<RevenueClosureWriter {...props} onRetained={() => callbacks++} />)); await terms(); await click("Conserver ce scénario");
      assert.equal(callbacks, 0); assert.ok(sessionStorage.getItem(storage)); assert.doesNotMatch(document.body.textContent!, /Valorisation conservée et relue/);
      if (mode === "rejection") { assert.equal(reads, 1); await click("Vérifier la clé avant correction"); assert.equal(reads, 2); assert.equal(sessionStorage.getItem(storage), null); assert.equal(document.querySelector("select")!.value, ""); }
    } finally { await act(async () => root.unmount()); }
  }
});
test("context change resets unsubmitted choices, duplicate clicks and late session lookup cannot POST", async () => {
  sessionStorage.clear(); setAccessToken(token()); const root = createRoot(document.getElementById("root")!); let calls = 0, resolve: (r: Response) => void = () => {};
  globalThis.fetch = () => { calls++; return new Promise<Response>(r => { resolve = r; }); };
  try {
    await act(async () => root.render(<RevenueClosureWriter {...props} />)); await terms();
    await act(async () => root.render(<RevenueClosureWriter {...props} reference={undefined} />)); assert.equal(document.querySelector("select")!.value, ""); assert.equal(document.querySelector("textarea")!.value, "");
    await act(async () => root.render(<RevenueClosureWriter {...props} />)); await terms();
    await act(async () => { button("Conserver ce scénario").click(); button("Conserver ce scénario").click(); }); assert.equal(calls, 1);
    setAccessToken(token("accueil")); await act(async () => resolve(reply(null))); assert.equal(calls, 1); assert.ok(sessionStorage.getItem(storage));
    await act(async () => root.render(<RevenueClosureWriter {...props} />)); assert.equal(document.querySelector("button"), null);
  } finally { await act(async () => root.unmount()); sessionStorage.clear(); }
});
test("corrupt local request and pending old-institute reads cannot revive source facts", async () => {
  sessionStorage.clear(); sessionStorage.setItem(storage, "bad"); setAccessToken(token()); const root = createRoot(document.getElementById("root")!); let calls = 0, resolve: (r: Response) => void = () => {};
  globalThis.fetch = () => { calls++; return new Promise<Response>(r => { resolve = r; }); };
  try {
    await act(async () => root.render(<RevenueClosureWriter {...props} />)); assert.match(document.body.textContent!, /demande locale est illisible/); assert.equal(button("Conserver ce scénario").disabled, true); assert.equal(calls, 0);
    await act(async () => root.render(<RevenueBookingClosures institute="own" timezone="UTC" />)); const dates = document.querySelectorAll<HTMLInputElement>('input[type="date"]'); await input(dates[0], "2026-01-01"); await input(dates[1], "2026-01-03");
    await act(async () => button("Lire les événements terminaux").click()); await act(async () => root.render(<RevenueBookingClosures institute="other" timezone="UTC" />));
    await act(async () => resolve(reply(vector.closure_report))); assert.doesNotMatch(document.body.textContent!, /Événement closure/); assert.equal(calls, 1);
  } finally { await act(async () => root.unmount()); sessionStorage.clear(); }
});
