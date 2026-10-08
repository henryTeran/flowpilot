import test from "node:test";
import assert from "node:assert/strict";
import React, { act } from "react";
import { JSDOM } from "jsdom";
import { readFileSync } from "node:fs";
import { BaseCancellationPanel } from "../src/components/BaseCancellationPanel";
import { setAccessToken } from "../src/api/session";
import { revenueOriginalFingerprint as hash } from "../src/revenue-scenario-utils";
import { baseCancellationIntentKey } from "../src/base-cancellation-intent";
const f = JSON.parse(readFileSync(new URL("./fixtures/base-cancellation-17i.json", import.meta.url), "utf8"));
const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (role = "responsable_institut") => `h.${Buffer.from(JSON.stringify({ sub: "signed-manager", role })).toString("base64url")}.s`;
const reply = (value: unknown) => new Response(JSON.stringify(value), { headers: { "Content-Type": "application/json" } });
const appointments = [{ id: "appointment", institute_id: "own", status: "scheduled", start_time: f.preview.appointment.start_time, customer_name: "Cliente test" }] as any;
async function settle() { for (let i = 0; i < 500 && document.querySelector('[role="status"]'); i++) await act(async () => new Promise(r => setTimeout(r, 10))); assert.equal(document.querySelector('[role="status"]'), null); }
async function click(name: string) { const b = Array.from(document.querySelectorAll("button")).find(b => b.textContent === name)!; assert.ok(b, name); assert.equal(b.disabled, false, name); await act(async () => b.click()); await settle(); }
async function fill(label: string, value: string) {
  const input = Array.from(document.querySelectorAll("label")).find(l => l.textContent?.startsWith(label))!.querySelector("input,select") as HTMLInputElement;
  const proto = input.tagName === "SELECT" ? dom.window.HTMLSelectElement.prototype : dom.window.HTMLInputElement.prototype;
  await act(async () => { Object.getOwnPropertyDescriptor(proto, "value")!.set!.call(input, value); input.dispatchEvent(new dom.window.Event(input.tagName === "SELECT" ? "change" : "input", { bubbles: true })); });
}
function backend() {
  let op: any = null, decision: any = null, execution: any = null;
  const writes: string[] = [], reads: string[] = [];
  let lost = false, tamper = false;
  const envelope = async (original: any) => ({ original, fingerprint: await hash(original) });
  const state = () => ({ ...structuredClone(f.pending), operation: op, decisions: decision ? [decision] : [], status: decision ? "approved" : "pending" });
  globalThis.fetch = async (url, init) => {
    const path = String(url).split("?")[0], request = init?.body ? JSON.parse(init.body as string) : undefined;
    if (init?.method === "POST") {
      writes.push(path);
      if (path.endsWith("/appointment-cancel")) { assert.deepEqual(request, { appointment_id: "appointment" }); return reply(f.preview); }
      const mode = path.endsWith("/sensitive-operations") ? "operation" : path.endsWith("/approvals") ? "decision" : "execution";
      assert.deepEqual(JSON.parse(sessionStorage.getItem(baseCancellationIntentKey("own", "signed-manager", mode))!).terms, request);
      assert.equal(request.actor_id, undefined); assert.equal(request.approved, undefined);
      if (mode === "operation") { op = await envelope({ ...structuredClone(f.pending.operation.original), ...request }); if (lost) throw new TypeError("lost acknowledgement"); return reply(op); }
      if (mode === "decision") { decision = await envelope({ ...structuredClone(f.approved.decisions[0].original), ...request, actor_id: "signed-manager" }); return reply(decision); }
      execution = await envelope({ ...structuredClone(f.execution.original), ...request }); return reply(execution);
    }
    reads.push(path);
    if (path.endsWith("/approval-state")) return reply(tamper ? { ...state(), status: "revoked" } : state());
    if (path.endsWith("/approval-by-key")) return reply(decision);
    if (path.endsWith("/execution-by-key") || path.endsWith("/execution")) return reply(execution);
    return reply(op);
  };
  return { writes, reads, lose: () => { lost = true; }, tamper: () => { tamper = true; } };
}
const render = (root: ReturnType<typeof createRoot>, institute = "own") => act(async () => root.render(<BaseCancellationPanel institute={institute} timezone="Europe/Zurich" appointments={appointments} />));
async function prepare() {
  await fill("Rendez-vous à relire", "appointment"); await click("Relire avant préparation");
  await fill("Validité jusqu’au", "2030-10-08T14:00"); await fill("Motif de l’action", "Annulation relue explicitement");
  await click("Conserver la préparation");
}
test("DOM: no mount calls or implicit selection; explicit prepare approve execute with independent receipts", async () => {
  sessionStorage.clear(); setAccessToken(token()); const h = backend(), root = createRoot(document.getElementById("root")!);
  try {
    await render(root); assert.equal(h.writes.length + h.reads.length, 0); assert.equal(document.querySelector<HTMLSelectElement>("select")!.value, "");
    await prepare(); assert.match(document.body.textContent!, /en attente/); assert.equal(h.writes.length, 2);
    assert.equal(document.body.textContent!.includes("Exécuter l’annulation approuvée"), false);
    await fill("Motif de l’action", "Approbation humaine explicite"); await click("Approuver cette préparation");
    assert.equal(h.writes.length, 3); assert.match(document.body.textContent!, /approuvée/);
    await fill("Motif de l’action", "Exécution humaine explicite"); await click("Exécuter l’annulation approuvée");
    assert.equal(h.writes.length, 4); assert.match(document.body.textContent!, /Annulation exécutée et preuve relue/);
    assert.equal(document.body.textContent!.includes("Révoquer l’approbation"), false);
  } finally { await act(async () => root.unmount()); }
});
test("DOM: lost preparation acknowledgement reload freezes terms and explicit recovery sends no second POST", async () => {
  sessionStorage.clear(); setAccessToken(token()); const h = backend(); h.lose(); let root = createRoot(document.getElementById("root")!);
  try {
    await render(root); await prepare(); assert.match(document.body.textContent!, /Demande conservée/);
    const writes = h.writes.length; await act(async () => root.unmount()); root = createRoot(document.getElementById("root")!);
    await render(root); await click("Reprendre la préparation"); assert.equal(h.writes.length, writes);
    assert.match(document.body.textContent!, /Préparation conservée/); assert.equal(sessionStorage.getItem(baseCancellationIntentKey("own", "signed-manager", "operation")), null);
  } finally { await act(async () => root.unmount()); }
});
test("DOM: corrupt fresh decision history masks action authority and retains exact operation reference for retry", async () => {
  sessionStorage.clear(); setAccessToken(token()); const h = backend(), root = createRoot(document.getElementById("root")!);
  try {
    await render(root); await prepare(); h.tamper(); await click("Relire préparation et décisions");
    assert.ok(document.querySelector('[role="alert"]')); assert.equal(document.body.textContent!.includes("Approuver cette préparation"), false);
    assert.equal(document.body.textContent!.includes("Exécuter l’annulation approuvée"), false); assert.equal(h.writes.length, 2);
  } finally { await act(async () => root.unmount()); }
});
test("DOM: reception has no panel or I/O; late old-token preview cannot publish", async () => {
  sessionStorage.clear(); setAccessToken(token("accueil")); const root = createRoot(document.getElementById("root")!); let calls = 0, release!: () => void;
  globalThis.fetch = async () => { calls++; return reply(null); };
  try {
    await render(root); assert.equal(document.querySelector("section"), null); assert.equal(calls, 0);
    setAccessToken(token()); await render(root); await fill("Rendez-vous à relire", "appointment");
    globalThis.fetch = async () => new Promise(resolve => { release = () => resolve(reply(f.preview)); });
    const b = Array.from(document.querySelectorAll("button")).find(b => b.textContent === "Relire avant préparation")!;
    await act(async () => b.click()); setAccessToken(token("accueil")); await render(root); await act(async () => release());
    assert.equal(document.querySelector("section"), null);
  } finally { await act(async () => root.unmount()); }
});
