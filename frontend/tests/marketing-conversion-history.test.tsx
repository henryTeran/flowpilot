import test from "node:test";
import assert from "node:assert/strict";
import React, { act } from "react";
import { JSDOM } from "jsdom";
import { readFileSync } from "node:fs";
import { MarketingConversionHistory } from "../src/components/MarketingConversionHistory";
import { setAccessToken } from "../src/api/session";
const v = JSON.parse(readFileSync(new URL("./fixtures/marketing-conversions-13bb.json", import.meta.url), "utf8"));
const a = v.linked.attribution;
const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (role = "responsable_institut") => `h.${Buffer.from(JSON.stringify({ sub: "manager", role })).toString("base64url")}.s`;
const reply = (v: unknown) => new Response(JSON.stringify(v), { headers: { "Content-Type": "application/json" } });
async function click() {
  await act(async () => [...document.querySelectorAll("button")].find(b => b.textContent === "Vérifier l’historique des conversions")!.click());
  for (let n = 0; n < 200 && document.querySelector('[role="status"]'); n++) await act(async () => { await new Promise(r => setTimeout(r, 10)); });
}
const component = () => <MarketingConversionHistory institute={v.institute_id} ticket={a.ticket.ticket_id} />;
test("explicit historical read verifies independent original/source copies, displays retraction and hides corrupted history", async () => {
  sessionStorage.clear(); setAccessToken(token()); const root = createRoot(document.getElementById("root")!);
  let reads = 0, corrupt = false;
  globalThis.fetch = async url => {
    reads++; const path = String(url);
    if (path.includes("/audit?")) return reply(v.audit);
    if (path.endsWith("/current")) return reply(v.retracted);
    if (path.includes("/conversions/")) return reply([v.linked, v.retracted].find(o => path.endsWith(o.id) || path.endsWith(o.request.idempotency_key)));
    if (path.includes("/campaigns/")) return reply(a.authorization);
    if (path.includes("/outcomes/")) return reply(a.accepted);
    return reply(corrupt ? { ...a.intent, request_fingerprint: "0".repeat(64) } : a.intent);
  };
  try {
    await act(async () => root.render(component())); assert.equal(reads, 0);
    await click(); assert.match(document.body.textContent!, /Lien courant rétracté/);
    assert.match(document.body.textContent!, /2 décisions conservées/); assert.match(document.body.textContent!, /123\.45 CHF/);
    assert.match(document.body.textContent!, /other-manager/);
    corrupt = true; await click(); assert.ok(document.querySelector('[role="alert"]'));
    assert.doesNotMatch(document.body.textContent!, /123\.45 CHF/);
    corrupt = false; await click(); assert.match(document.body.textContent!, /Lien courant rétracté/);
    setAccessToken(token("accueil")); await act(async () => root.render(component()));
    assert.equal(document.querySelector("button"), null);
  } finally { await act(async () => root.unmount()); }
});
test("current-head changes during independent history verification refuse publication", async () => {
  sessionStorage.clear(); setAccessToken(token()); const root = createRoot(document.getElementById("root")!);
  let heads = 0;
  globalThis.fetch = async url => {
    const path = String(url);
    if (path.endsWith("/current")) return reply(++heads === 1 ? v.retracted : v.linked);
    if (path.includes("/audit?")) return reply(v.audit);
    if (path.includes("/conversions/")) return reply([v.linked, v.retracted].find(o => path.endsWith(o.id) || path.endsWith(o.request.idempotency_key)));
    if (path.includes("/campaigns/")) return reply(a.authorization);
    if (path.includes("/outcomes/")) return reply(a.accepted);
    return reply(a.intent);
  };
  try {
    await act(async () => root.render(component())); await click();
    assert.equal(heads, 2); assert.ok(document.querySelector('[role="alert"]'));
    assert.doesNotMatch(document.body.textContent!, /décisions conservées/);
  } finally { await act(async () => root.unmount()); }
});
