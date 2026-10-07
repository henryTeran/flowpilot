import test from "node:test";
import assert from "node:assert/strict";
import React, { act } from "react";
import { JSDOM } from "jsdom";
import { readFileSync } from "node:fs";
import { RevenueScenarioWriter } from "../src/components/RevenueScenarioWriter";
import { revenueOriginalFingerprint, type RevenueScenarioDeclaration } from "../src/revenue-scenario-utils";
import { setAccessToken } from "../src/api/session";
const vector = JSON.parse(readFileSync(new URL("./fixtures/revenue-scenario-14o.json", import.meta.url), "utf8"));
const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (role = "responsable_institut") => `h.${Buffer.from(JSON.stringify({ sub: "manager", role })).toString("base64url")}.s`;
const storage = 'flowpilot.revenue-scenario.v1:["own","manager"]';
const reply = (v: unknown, status = 200) => new Response(JSON.stringify(v), { status, headers: { "Content-Type": "application/json" } });
const button = (text: string) => Array.from(document.querySelectorAll("button")).find(b => b.textContent!.includes(text))!;
async function click(text: string, settle = true) {
  await act(async () => button(text).click());
  if (settle) {
    for (let n = 0; n < 250 && document.querySelector('[role="status"]'); n++) await act(async () => { await new Promise(resolve => setTimeout(resolve, 20)); });
    assert.equal(document.querySelector('[role="status"]'), null);
  }
}
async function draft() {
  const inputs = Array.from(document.querySelectorAll("input"));
  for (const [i, value] of ["2026-01-01", "2026-01-03", "2026-01-04", "2026-01-07", "1", "3"].entries()) {
    await act(async () => { Object.getOwnPropertyDescriptor(dom.window.HTMLInputElement.prototype, "value")!.set!.call(inputs[i], value); inputs[i].dispatchEvent(new dom.window.Event("input", { bubbles: true })); inputs[i].dispatchEvent(new dom.window.Event("change", { bubbles: true })); });
  }
  await act(async () => { const select = document.querySelector("select")!; select.value = "CHF"; select.dispatchEvent(new dom.window.Event("change", { bubbles: true })); });
  await act(async () => { const area = document.querySelector("textarea")!; Object.getOwnPropertyDescriptor(dom.window.HTMLTextAreaElement.prototype, "value")!.set!.call(area, "Scénario 😀\nMotif explicite"); area.dispatchEvent(new dom.window.Event("input", { bubbles: true })); });
}
async function envelope(terms: RevenueScenarioDeclaration) {
  const e = structuredClone(vector); Object.assign(e.original, { assumptions: terms.assumptions, reason: terms.reason, idempotency_key: terms.idempotency_key, actor_id: "manager" });
  e.original.evidence.window.start = terms.assumptions.observed_start; e.original.evidence.window.end = terms.assumptions.observed_end;
  e.fingerprint = await revenueOriginalFingerprint(e.original); return e;
}
test("lost acknowledgement persists frozen terms before POST and recovers after remount without a second POST", async () => {
  sessionStorage.clear(); setAccessToken(token()); let root = createRoot(document.getElementById("root")!);
  let retained: any = null, posts = 0, reads = 0, callbacks = 0;
  globalThis.fetch = async (_url, init) => {
    if (init?.method === "POST") {
      posts++; const terms = JSON.parse(init.body as string); assert.deepEqual(JSON.parse(sessionStorage.getItem(storage)!).terms, terms);
      retained = await envelope(terms); throw new TypeError("lost acknowledgement");
    }
    reads++; return reply(retained);
  };
  try {
    await act(async () => root.render(<RevenueScenarioWriter institute="own" timezone="UTC" onRetained={() => callbacks++} />)); assert.equal(reads, 0);
    await draft(); await click("Conserver ces hypothèses"); assert.equal(posts, 1); assert.equal(reads, 1); assert.ok(sessionStorage.getItem(storage));
    assert.ok(document.querySelector("input")!.disabled); assert.ok(document.querySelector('[role="alert"]'));
    await act(async () => root.unmount()); root = createRoot(document.getElementById("root")!);
    await act(async () => root.render(<RevenueScenarioWriter institute="own" timezone="UTC" onRetained={() => callbacks++} />)); assert.equal(reads, 1);
    await click("Reprendre"); assert.equal(posts, 1); assert.equal(reads, 4); assert.equal(callbacks, 1); assert.equal(sessionStorage.getItem(storage), null);
    assert.match(document.body.textContent!, /Scénario conservé et relu/); assert.match(document.body.textContent!, /101 \/ 2 centimes CHF/);
    await click("Déclarer un autre"); assert.equal(document.querySelector("input")!.disabled, false); assert.equal(document.querySelector("textarea")!.value, "");
  } finally { await act(async () => root.unmount()); }
});
test("independent receipt substitution refuses success and preserves original key", async () => {
  for (const mismatch of ["actor", "reason", "fraction", "id-read"]) {
    sessionStorage.clear(); setAccessToken(token()); const root = createRoot(document.getElementById("root")!); let retained: any = null, callbacks = 0;
    globalThis.fetch = async (url, init) => {
      if (init?.method === "POST") { retained = await envelope(JSON.parse(init.body as string)); return reply(retained); }
      if (!retained) return reply(null);
      const e = structuredClone(retained);
      if (mismatch !== "id-read" || String(url).includes("/originals/")) {
        if (mismatch === "actor") e.original.actor_id = "another-manager";
        if (mismatch === "reason") e.original.reason = "Other valid reason";
        if (mismatch === "fraction") { e.original.assumptions.activity_fraction.numerator = "0"; e.original.projected_gross_minor = { numerator: "0", denominator: "1" }; }
        if (mismatch === "id-read") e.original.id = "different-original";
        e.fingerprint = await revenueOriginalFingerprint(e.original);
      }
      return reply(e);
    };
    try {
      await act(async () => root.render(<RevenueScenarioWriter institute="own" timezone="UTC" onRetained={() => callbacks++} />)); await draft(); await click("Conserver ces hypothèses");
      assert.equal(callbacks, 0, mismatch); assert.ok(sessionStorage.getItem(storage), mismatch); assert.doesNotMatch(document.body.textContent!, /Scénario conservé et relu/);
    } finally { await act(async () => root.unmount()); }
  }
});
test("definitive rejection requires fresh absent-key verification before editing; invalid local state and roles never send", async () => {
  sessionStorage.clear(); setAccessToken(token()); const root = createRoot(document.getElementById("root")!); let calls = 0;
  globalThis.fetch = async (_url, init) => { calls++; return init?.method === "POST" ? reply({ detail: "invalid period" }, 422) : reply(null); };
  try {
    await act(async () => root.render(<RevenueScenarioWriter institute="own" timezone="UTC" />)); await click("Conserver ces hypothèses"); assert.equal(calls, 0);
    await draft(); await click("Conserver ces hypothèses"); assert.equal(calls, 2); assert.ok(sessionStorage.getItem(storage));
    await click("Vérifier la clé avant correction"); assert.equal(calls, 3); assert.equal(sessionStorage.getItem(storage), null); assert.equal(document.querySelector("input")!.disabled, false);
    sessionStorage.setItem(storage, "invalid"); await act(async () => root.render(<RevenueScenarioWriter institute="other" timezone="UTC" />));
    await act(async () => root.render(<RevenueScenarioWriter institute="own" timezone="UTC" />)); assert.match(document.body.textContent!, /demande locale est illisible/); assert.equal(button("Conserver ces hypothèses").disabled, true);
    setAccessToken(token("accueil")); await act(async () => root.render(<RevenueScenarioWriter institute="own" timezone="UTC" />)); assert.equal(document.querySelector("button"), null); assert.equal(calls, 3);
  } finally { await act(async () => root.unmount()); sessionStorage.clear(); }
});
test("double click and session replacement cannot post a pending key lookup", async () => {
  sessionStorage.clear(); setAccessToken(token()); const root = createRoot(document.getElementById("root")!); let calls = 0, resolve: (r: Response) => void = () => {};
  globalThis.fetch = () => { calls++; return new Promise<Response>(r => { resolve = r; }); };
  try {
    await act(async () => root.render(<RevenueScenarioWriter institute="own" timezone="UTC" />)); await draft();
    await act(async () => { button("Conserver ces hypothèses").click(); button("Conserver ces hypothèses").click(); }); assert.equal(calls, 1);
    setAccessToken(token("accueil")); await act(async () => { resolve(reply(null)); }); assert.equal(calls, 1); assert.ok(sessionStorage.getItem(storage));
    assert.doesNotMatch(document.body.textContent!, /Scénario conservé et relu/);
  } finally { await act(async () => root.unmount()); sessionStorage.clear(); }
});
