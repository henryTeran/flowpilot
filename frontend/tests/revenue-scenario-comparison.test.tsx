import test from "node:test";
import assert from "node:assert/strict";
import React, { act } from "react";
import { JSDOM } from "jsdom";
import { readFileSync } from "node:fs";
import { RevenueScenarioComparison } from "../src/components/RevenueScenarioComparison";
import { setAccessToken } from "../src/api/session";
const { frame, selection } = JSON.parse(readFileSync(new URL("./fixtures/revenue-comparison-14q.json", import.meta.url), "utf8"));
const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (role = "responsable_institut") => `h.${Buffer.from(JSON.stringify({ sub: "manager", role })).toString("base64url")}.s`;
const reply = (v: unknown) => new Response(JSON.stringify(v), { headers: { "Content-Type": "application/json" } });
const baseline = frame.variants[0].original, alternatives = [frame.variants[1].original];
const button = () => Array.from(document.querySelectorAll("button")).find(b => b.textContent === "Comparer la sélection")!;
async function settle() { for (let n = 0; n < 250 && document.querySelector('[role="status"]'); n++) await act(async () => { await new Promise(r => setTimeout(r, 20)); }); assert.equal(document.querySelector('[role="status"]'), null); }
test("explicit native comparison accepts pure Python frame, clears corrupt reread and never requests incomplete selection", async () => {
  setAccessToken(token()); const root = createRoot(document.getElementById("root")!); let calls = 0, bad = false;
  globalThis.fetch = async (_url, init) => { calls++; assert.equal(init?.method, "POST"); assert.deepEqual(JSON.parse(init?.body as string), selection); return reply(bad ? { ...frame, summed_projected_gross_minor: "101" } : frame); };
  try {
    await act(async () => root.render(<RevenueScenarioComparison institute="own" alternatives={[]} onRemove={() => {}} />)); assert.equal(button().disabled, true); assert.equal(calls, 0);
    await act(async () => root.render(<RevenueScenarioComparison institute="own" baseline={baseline} alternatives={alternatives} onRemove={() => {}} />)); assert.equal(calls, 0);
    await act(async () => button().click()); await settle(); assert.equal(calls, 1); assert.match(document.body.textContent!, /Écart à la référence : -101 \/ 2 centimes CHF/); assert.match(document.body.textContent!, /Projection conditionnelle : 0 \/ 1 centimes CHF/);
    bad = true; await act(async () => button().click()); await settle(); assert.ok(document.querySelector('[role="alert"]')); assert.doesNotMatch(document.body.textContent!, /Comparaison vérifiée/);
    bad = false; await act(async () => button().click()); await settle(); assert.match(document.body.textContent!, /Comparaison vérifiée/);
  } finally { await act(async () => root.unmount()); }
});
test("selection/session replacement and duplicate clicks cannot retain late comparison proof", async () => {
  setAccessToken(token()); const root = createRoot(document.getElementById("root")!); let calls = 0, resolve: (r: Response) => void = () => {};
  globalThis.fetch = () => { calls++; return new Promise<Response>(r => { resolve = r; }); };
  try {
    await act(async () => root.render(<RevenueScenarioComparison institute="own" baseline={baseline} alternatives={alternatives} onRemove={() => {}} />));
    await act(async () => { button().click(); button().click(); }); assert.equal(calls, 1);
    await act(async () => root.render(<RevenueScenarioComparison institute="own" baseline={baseline} alternatives={[]} onRemove={() => {}} />));
    await act(async () => { resolve(reply(frame)); await new Promise(r => setTimeout(r, 30)); }); assert.doesNotMatch(document.body.textContent!, /Comparaison vérifiée/);
    await act(async () => root.render(<RevenueScenarioComparison institute="own" baseline={baseline} alternatives={alternatives} onRemove={() => {}} />));
    setAccessToken(token("accueil")); await act(async () => button().click()); assert.equal(calls, 1);
    setAccessToken(token()); await act(async () => button().click()); assert.equal(calls, 2);
    setAccessToken(token("accueil")); await act(async () => { resolve(reply(frame)); await new Promise(r => setTimeout(r, 30)); }); assert.doesNotMatch(document.body.textContent!, /Comparaison vérifiée/);
    await act(async () => root.render(<RevenueScenarioComparison institute="own" baseline={baseline} alternatives={alternatives} onRemove={() => {}} />)); assert.equal(document.querySelector("button"), null);
  } finally { await act(async () => root.unmount()); }
});
