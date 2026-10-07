import test from "node:test";
import assert from "node:assert/strict";
import React, { act } from "react";
import { JSDOM } from "jsdom";
import { readFileSync } from "node:fs";
import { RevenueScenarioHistory } from "../src/components/RevenueScenarioHistory";
import { setAccessToken } from "../src/api/session";
const vector = JSON.parse(readFileSync(new URL("./fixtures/revenue-scenario-14o.json", import.meta.url), "utf8"));
const audit = { institute_id: "own", captured_at: vector.original.created_at, offset: 0, limit: 20, total: 1, originals: [vector], full_original_cohort_verified: true, complete_sales_history: false, action_executed: false };
const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (role = "responsable_institut") => `h.${Buffer.from(JSON.stringify({ sub: "manager", role })).toString("base64url")}.s`;
const reply = (v: unknown) => new Response(JSON.stringify(v), { headers: { "Content-Type": "application/json" } });
async function click(settle = false) {
  await act(async () => document.querySelector("button")!.click());
  if (settle) {
    for (let n = 0; n < 250 && document.querySelector('[role="status"]'); n++) await act(async () => { await new Promise(resolve => setTimeout(resolve, 20)); });
    assert.equal(document.querySelector('[role="status"]'), null);
  }
}
test("explicit history reads preserve full original SHA and refuse malformed rereads", async () => {
  setAccessToken(token()); const root = createRoot(document.getElementById("root")!); let calls = 0, bad = false;
  globalThis.fetch = async () => { calls++; return reply(bad ? { ...audit, full_original_cohort_verified: 1 } : audit); };
  try {
    await act(async () => root.render(<RevenueScenarioHistory institute="own" />)); assert.equal(calls, 0);
    await click(true); assert.equal(calls, 1); assert.match(document.body.textContent!, /101 \/ 2 centimes CHF/);
    assert.match(document.body.textContent!, /1\.01 CHF/);
    assert.match(document.body.textContent!, /Devise sélectionnée : CHF/);
    assert.ok(document.body.textContent!.includes(vector.fingerprint)); assert.match(document.body.textContent!, /Scénario 😀/);
    bad = true; await click(true); assert.ok(document.querySelector('[role="alert"]')); assert.doesNotMatch(document.body.textContent!, /101 \/ 2/);
    bad = false; await click(true); assert.match(document.body.textContent!, /101 \/ 2/);
  } finally { await act(async () => root.unmount()); }
});
test("session and institute replacement discard pending history and non-manager reads", async () => {
  setAccessToken(token()); const root = createRoot(document.getElementById("root")!); let resolve: (r: Response) => void = () => {};
  globalThis.fetch = () => new Promise<Response>(r => { resolve = r; });
  try {
    await act(async () => root.render(<RevenueScenarioHistory institute="own" />)); await click(); setAccessToken(token("accueil"));
    await act(async () => resolve(reply(audit))); assert.doesNotMatch(document.body.textContent!, /101 \/ 2/);
    setAccessToken(token()); await click(); await act(async () => root.render(<RevenueScenarioHistory institute="other" />));
    await act(async () => resolve(reply(audit))); assert.doesNotMatch(document.body.textContent!, /101 \/ 2/);
    setAccessToken(token("accueil")); await act(async () => root.render(<RevenueScenarioHistory institute="own" />)); assert.equal(document.querySelector("button"), null);
  } finally { await act(async () => root.unmount()); }
});
