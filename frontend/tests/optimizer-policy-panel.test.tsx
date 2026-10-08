import test from "node:test";
import assert from "node:assert/strict";
import React, { act } from "react";
import { JSDOM } from "jsdom";
import fixture from "./fixtures/optimizer-policy-16e.json";
import { OptimizerPolicyPanel, optimizerLabels } from "../src/components/OptimizerPolicyPanel";
import { optimizerFactors } from "../src/optimizer-policy-utils";
import { optimizerPolicyIntentKey } from "../src/optimizer-policy-intent";
import { revenueOriginalFingerprint } from "../src/revenue-scenario-utils";
import { setAccessToken } from "../src/api/session";
const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (role = "responsable_institut") => `h.${Buffer.from(JSON.stringify({ sub: "manager", role })).toString("base64url")}.s`;
const key = optimizerPolicyIntentKey("own", "manager");
const reply = (value: unknown) => new Response(JSON.stringify(value), { headers: { "Content-Type": "application/json" } });
async function settle() { for (let i = 0; i < 500 && document.querySelector<HTMLButtonElement>("button:disabled") && document.querySelector('[role="status"]'); i++) await act(async () => new Promise(r => setTimeout(r, 10))); }
async function click(name: string) { const b = Array.from(document.querySelectorAll("button")).find(b => b.textContent === name)!; assert.ok(b, name); await act(async () => b.click()); }
async function fill(label: string, value: string) {
  const input = Array.from(document.querySelectorAll("label")).find(l => l.textContent?.startsWith(label))!.querySelector("input,select,textarea") as HTMLInputElement;
  assert.ok(input, label);
  const proto = input.tagName === "SELECT" ? dom.window.HTMLSelectElement.prototype : input.tagName === "TEXTAREA" ? dom.window.HTMLTextAreaElement.prototype : dom.window.HTMLInputElement.prototype;
  await act(async () => { Object.getOwnPropertyDescriptor(proto, "value")!.set!.call(input, value); input.dispatchEvent(new dom.window.Event(input.tagName === "SELECT" ? "change" : "input", { bubbles: true })); });
}
async function draft() {
  for (const f of optimizerFactors) { await fill(`Statut — ${optimizerLabels[f]}`, f === "utilization_score" ? "enabled" : "disabled"); await fill(`Motif — ${optimizerLabels[f]}`, "Choix explicite relu"); }
  await fill(`Numérateur du poids — ${optimizerLabels.utilization_score}`, "1"); await fill(`Dénominateur du poids — ${optimizerLabels.utilization_score}`, "1");
  await fill("Motif de la politique", "Politique test explicite");
}
async function envelope(request: any) {
  const e = structuredClone(fixture["0"].originals[0]); Object.assign(e.original, request, { actor_id: "manager" });
  e.fingerprint = await revenueOriginalFingerprint(e.original); return e;
}
const render = (root: ReturnType<typeof createRoot>, extra: Partial<React.ComponentProps<typeof OptimizerPolicyPanel>> = {}) => act(async () => root.render(<OptimizerPolicyPanel institute="own" timezone="Europe/Zurich" {...extra} />));

test("explicit policy form has no mount I/O or defaults and confirms frozen terms through independent reads", async () => {
  sessionStorage.clear(); setAccessToken(token()); const root = createRoot(document.getElementById("root")!); let retained: unknown = null, calls = 0, posts = 0;
  globalThis.fetch = async (_url, init) => { calls++; if (init?.method === "POST") { posts++; const terms = JSON.parse(init.body as string); assert.deepEqual(JSON.parse(sessionStorage.getItem(key)!).terms, terms); retained = await envelope(terms); } return reply(retained); };
  try {
    await render(root); assert.equal(calls, 0); assert.equal(document.querySelector<HTMLSelectElement>("select")!.value, "");
    await click("Conserver la politique et relire l’original"); assert.equal(calls, 0); assert.ok(document.querySelector('[role="alert"]'));
    await draft(); await click("Conserver la politique et relire l’original"); await settle();
    assert.equal(posts, 1); assert.equal(calls, 4); assert.equal(sessionStorage.getItem(key), null);
    assert.match(document.body.textContent!, /Politique conservée et relue/); assert.match(document.body.textContent!, /désactivé explicitement/);
    await click("Préparer une autre politique"); assert.equal(document.querySelector<HTMLSelectElement>("select")!.value, "");
  } finally { await act(async () => root.unmount()); }
});
test("lost acknowledgement survives native panel reload and recovers without another POST", async () => {
  sessionStorage.clear(); setAccessToken(token()); let root = createRoot(document.getElementById("root")!), retained: unknown = null, posts = 0, reads = 0;
  globalThis.fetch = async (_url, init) => { if (init?.method === "POST") { posts++; retained = await envelope(JSON.parse(init.body as string)); throw new TypeError("lost"); } reads++; return reply(retained); };
  try {
    await render(root); await draft(); await click("Conserver la politique et relire l’original"); await settle(); assert.equal(posts, 1); assert.ok(sessionStorage.getItem(key));
    await act(async () => root.unmount()); root = createRoot(document.getElementById("root")!); await render(root);
    const before = reads; await click("Reprendre la politique par clé"); await settle();
    assert.equal(posts, 1); assert.equal(reads-before, 3); assert.equal(sessionStorage.getItem(key), null); assert.match(document.body.textContent!, /Politique conservée et relue/);
  } finally { await act(async () => root.unmount()); }
});
test("history pages verify replies, select an explicit original, mask tamper and support retry", async () => {
  sessionStorage.clear(); setAccessToken(token()); const root = createRoot(document.getElementById("root")!); let calls = 0, value: unknown, selected: unknown;
  globalThis.fetch = async url => { calls++; return reply(value ?? (String(url).includes("offset=20") ? fixture["20"] : fixture["0"])); };
  try {
    await render(root, { onSelect: p => selected = p }); assert.equal(calls, 0);
    await click("Lire les politiques conservées"); await settle(); assert.equal(document.querySelectorAll("article").length, 20);
    await click("Choisir cette politique pour la revue"); await act(async () => new Promise(r => setTimeout(r, 25))); assert.ok(selected);
    await click("Politiques suivantes"); await settle(); assert.equal(document.querySelectorAll("article").length, 5); assert.equal(selected, undefined);
    value = { ...fixture["0"], basis: "active_default" }; await click("Lire les politiques conservées"); await settle(); assert.equal(document.querySelectorAll("article").length, 0); assert.ok(document.querySelector('[role="alert"]'));
    value = undefined; await click("Lire les politiques conservées"); await settle(); assert.equal(document.querySelectorAll("article").length, 20);
  } finally { await act(async () => root.unmount()); }
});
test("changed institute or session suppresses late history and manager controls", async () => {
  sessionStorage.clear(); setAccessToken(token()); const root = createRoot(document.getElementById("root")!); let resolve!: (value: Response) => void, calls = 0;
  globalThis.fetch = async () => { calls++; return new Promise<Response>(r => resolve = r); };
  try {
    await render(root); await click("Lire les politiques conservées"); await render(root, { institute: "other" });
    await act(async () => resolve(reply(fixture["0"]))); assert.equal(document.querySelector("article"), null); assert.equal(calls, 1);
    await render(root); await click("Lire les politiques conservées"); setAccessToken(token("accueil")); await act(async () => resolve(reply(fixture["0"])));
    assert.equal(document.querySelector("article"), null); await render(root); assert.equal(document.querySelector("section"), null);
  } finally { await act(async () => root.unmount()); }
});
