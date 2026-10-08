import test from "node:test";
import assert from "node:assert/strict";
import React, { act } from "react";
import { JSDOM } from "jsdom";
import fixture from "./fixtures/waitlist-lifecycle-15j.json";
import { WaitlistLifecycleWriter, type WaitlistLifecycleChoice } from "../src/components/WaitlistLifecycleWriter";
import { setAccessToken } from "../src/api/session";
import { waitlistLifecycleIntentKey } from "../src/waitlist-lifecycle-intent";
import { revenueOriginalFingerprint } from "../src/revenue-scenario-utils";
import type { WaitlistLifecycleEnvelope, WaitlistLifecycleState } from "../src/waitlist-lifecycle-utils";
const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (role = "responsable_institut") => `h.${Buffer.from(JSON.stringify({ sub: "manager", role })).toString("base64url")}.s`;
const key = waitlistLifecycleIntentKey("own", "manager"), rootChoice = () => ({ kind: "root", envelope: fixture.activated.root }) as WaitlistLifecycleChoice;
const targetChoice = () => ({ kind: "target", envelope: fixture.revised.current_demand }) as WaitlistLifecycleChoice;
const reply = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { "Content-Type": "application/json" } });
function button(name: string) { const found = Array.from(document.querySelectorAll("button")).find(b => b.textContent!.includes(name)); assert.ok(found, name); return found; }
async function settle() { for (let n = 0; n < 500 && document.querySelector('[role="status"]'); n++) await act(async () => new Promise(r => setTimeout(r, 10))); assert.equal(document.querySelector('[role="status"]'), null); }
async function click(name: string, wait = true) { await act(async () => button(name).click()); if (wait) await settle(); }
async function reason(value = "Décision explicite avec cliente") { await act(async () => { const input = document.querySelector("textarea")!;
  Object.getOwnPropertyDescriptor(dom.window.HTMLTextAreaElement.prototype, "value")!.set!.call(input, value); input.dispatchEvent(new dom.window.Event("input", { bubbles: true })); }); }
async function render(root: ReturnType<typeof createRoot>, props: Partial<React.ComponentProps<typeof WaitlistLifecycleWriter>> = {}, wait = true) {
  await act(async () => root.render(<WaitlistLifecycleWriter institute="own" timezone="Europe/Zurich" {...props} />)); if (wait) await settle();
}
function server() {
  let state: WaitlistLifecycleState | null = null, calls = 0, posts = 0, reject = false, lost = false;
  const retained = new Map<string, WaitlistLifecycleEnvelope>();
  globalThis.fetch = async (url, init) => {
    calls++; const path = String(url);
    if (init?.method === "POST") {
      posts++; const request = JSON.parse(init.body as string); assert.deepEqual(JSON.parse(sessionStorage.getItem(key)!).terms.request, request);
      const previous = state?.events[state.events.length-1];
      if (reject || request.previous_id !== (previous?.original.id || null) || request.previous_fingerprint !== (previous?.fingerprint || null)) return reply({ detail: "version changed" }, 400);
      const sample = request.action === "activate" ? fixture.activated.events[0] : request.action === "revise" ? fixture.revised.events[1] : fixture.cancelled.events[2];
      const envelope = structuredClone(sample) as WaitlistLifecycleEnvelope; Object.assign(envelope.original, request, { actor_id: "manager" });
      envelope.fingerprint = await revenueOriginalFingerprint(envelope.original); retained.set(request.idempotency_key, envelope);
      const target = request.target_id === fixture.activated.root.original.id ? fixture.activated.root : fixture.revised.current_demand;
      state = { root: fixture.activated.root, current_demand: target, state: request.action === "cancel" ? "cancelled" : "active", events: [...(state?.events || []), envelope] } as WaitlistLifecycleState;
      if (lost) { lost = false; throw new TypeError("lost acknowledgement"); } return reply(envelope);
    }
    if (path.includes("original-by-key")) return reply(retained.get(new URL(path).searchParams.get("key")!) || null);
    if (path.includes("/lifecycle/originals/")) return reply([...retained.values()].find(e => path.endsWith(e.original.id)));
    if (path.includes("/lifecycle/states/")) return state ? reply(state) : reply({ detail: "not activated" }, 404);
    return reply(path.endsWith(fixture.revised.current_demand.original.id) ? fixture.revised.current_demand
      : path.endsWith(fixture.audit.states[1].root.original.id) ? fixture.audit.states[1].root : fixture.activated.root);
  };
  return { calls: () => calls, posts: () => posts, state: () => state, reject: (value: boolean) => { reject = value; }, lose: () => { lost = true; }, setState: (value: WaitlistLifecycleState) => { state = value; } };
}
test("native explicit activation, same-customer revision and terminal cancellation pin and reread source decisions", async () => {
  sessionStorage.clear(); setAccessToken(token()); const root = createRoot(document.getElementById("root")!); const api = server(); let callbacks = 0;
  try {
    await render(root); assert.equal(api.calls(), 0);
    await render(root, { choice: rootChoice(), onRetained: () => callbacks++ }); assert.equal(api.calls(), 2);
    assert.equal(document.activeElement, document.querySelector('[aria-label="Gérer une liste d’attente"]'));
    await click("Activer cette demande"); assert.equal(api.posts(), 0); assert.equal(sessionStorage.getItem(key), null);
    await reason(); await click("Activer cette demande"); assert.equal(api.posts(), 1); assert.equal(callbacks, 1); assert.match(document.body.textContent!, /Action conservée et relue/);
    await render(root, { choice: targetChoice(), onRetained: () => callbacks++ }); await reason("Révision demandée par cliente"); await click("Réviser avec la déclaration");
    assert.equal(api.posts(), 2); assert.equal(callbacks, 2); assert.equal(api.state()!.current_demand.original.id, fixture.revised.current_demand.original.id);
    await reason("Annulation demandée par cliente"); await click("Annuler cette liste"); assert.equal(api.posts(), 3); assert.equal(callbacks, 3);
    assert.equal(api.state()!.state, "cancelled"); assert.equal(api.state()!.events.length, 3); assert.equal(sessionStorage.getItem(key), null);
    assert.match(document.body.textContent!, /aucune nouvelle transition possible/); assert.equal(document.querySelector("textarea"), null);
    assert.equal(Array.from(document.querySelectorAll("button")).some(b => /Activer|Réviser|Annuler/.test(b.textContent!)), false);
  } finally { await act(async () => root.unmount()); }
});
test("lost native revision acknowledgement freezes source selection and reload recovers without another POST", async () => {
  sessionStorage.clear(); setAccessToken(token()); let root = createRoot(document.getElementById("root")!); const api = server(); let callbacks = 0;
  try {
    await render(root, { choice: rootChoice() }); await reason(); await click("Activer cette demande");
    await render(root, { choice: targetChoice() }); await reason("Révision à reprendre"); api.lose(); await click("Réviser avec la déclaration");
    assert.equal(api.posts(), 2); assert.ok(sessionStorage.getItem(key)); assert.match(document.body.textContent!, /Décision figée à reprendre/);
    assert.equal(document.querySelector("textarea"), null); assert.ok(document.querySelector('[role="alert"]'));
    await act(async () => root.unmount()); root = createRoot(document.getElementById("root")!); const calls = api.calls();
    await render(root, { onRetained: () => callbacks++ }); assert.equal(api.calls(), calls);
    await click("Reprendre l’action par clé"); assert.equal(api.posts(), 2); assert.equal(api.calls()-calls, 4); assert.equal(callbacks, 1);
    assert.equal(sessionStorage.getItem(key), null); assert.match(document.body.textContent!, /Action conservée et relue/); assert.match(document.body.textContent!, /Révision à reprendre/);
  } finally { await act(async () => root.unmount()); }
});
test("a stale native predecessor is rejected and correction requires fresh key then explicit source reselection", async () => {
  sessionStorage.clear(); setAccessToken(token()); const root = createRoot(document.getElementById("root")!); const api = server();
  try {
    await render(root, { choice: rootChoice() }); await reason(); await click("Activer cette demande"); await reason("Annuler une version relue");
    api.reject(true); await click("Annuler cette liste"); assert.ok(sessionStorage.getItem(key)); assert.equal(document.querySelector("textarea"), null);
    const calls = api.calls(); await click("Vérifier la clé avant de relire"); assert.equal(api.calls()-calls, 1); assert.equal(sessionStorage.getItem(key), null);
    assert.equal(document.querySelector("textarea"), null); assert.equal(document.querySelector("article"), null);
    api.reject(false); await render(root, { choice: rootChoice() }); assert.equal(document.querySelector<HTMLTextAreaElement>("textarea")!.value, "");
    await reason("Annulation après relecture"); await click("Annuler cette liste"); assert.equal(api.state()!.state, "cancelled");
  } finally { await act(async () => root.unmount()); }
});
test("foreign-customer replacement, malformed saved decision and roles cannot send native transitions", async () => {
  sessionStorage.clear(); setAccessToken(token()); const root = createRoot(document.getElementById("root")!); const api = server();
  try {
    await render(root, { choice: rootChoice() }); await reason(); await click("Activer cette demande"); const posts = api.posts();
    const foreign = fixture.audit.states[1].root;
    await render(root, { choice: { kind: "target", envelope: foreign } }); assert.ok(document.querySelector('[role="alert"]')); assert.equal(api.posts(), posts);
    sessionStorage.setItem(key, "broken"); await render(root, { timezone: "UTC" }); assert.match(document.body.textContent!, /locale est illisible/);
    assert.equal(document.querySelector("button"), null);
    setAccessToken(token("accueil")); await render(root); assert.equal(document.querySelector("section"), null); assert.equal(api.posts(), posts);
  } finally { await act(async () => root.unmount()); }
});
test("late native selection and action replies are rejected after scope or authority change", async () => {
  sessionStorage.clear(); setAccessToken(token()); const root = createRoot(document.getElementById("root")!); let release!: (value: Response) => void, calls = 0, callbacks = 0;
  globalThis.fetch = async () => { calls++; return new Promise<Response>(r => { release = r; }); };
  try {
    await render(root, { choice: rootChoice() }, false); while (!release) await act(async () => new Promise(r => setTimeout(r, 10)));
    await render(root, { institute: "other" }); await act(async () => release(reply(fixture.activated.root))); assert.equal(calls, 1); assert.equal(document.querySelector("article"), null);
    const api = server(); await render(root, { choice: rootChoice(), onRetained: () => callbacks++ }); await reason();
    globalThis.fetch = async () => { calls++; return new Promise<Response>(r => { release = r; }); };
    const prior = calls; await click("Activer cette demande", false);
    for (let n = 0; n < 500 && calls === prior; n++) await act(async () => new Promise(r => setTimeout(r, 10)));
    assert.ok(calls > prior); assert.ok(sessionStorage.getItem(key));
    const before = calls; setAccessToken(token("accueil")); await act(async () => release(reply(null)));
    assert.equal(callbacks, 0); assert.equal(calls, before); assert.ok(sessionStorage.getItem(key)); assert.equal(api.posts(), 0);
    await render(root); assert.equal(document.querySelector("section"), null);
  } finally { await act(async () => root.unmount()); }
});
