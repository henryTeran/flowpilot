import test from "node:test";
import assert from "node:assert/strict";
import React, { act } from "react";
import { JSDOM } from "jsdom";
import { readFileSync } from "node:fs";
import { MarketingCurrentConversions } from "../src/components/MarketingCurrentConversions";
import { setAccessToken } from "../src/api/session";
const v = JSON.parse(readFileSync(new URL("./fixtures/marketing-conversions-13bb.json", import.meta.url), "utf8"));
const a = v.linked.attribution;
const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (role = "responsable_institut") => `h.${Buffer.from(JSON.stringify({ sub: "manager", role })).toString("base64url")}.s`;
const reply = (v: unknown) => new Response(JSON.stringify(v), { headers: { "Content-Type": "application/json" } });
async function click() {
  await act(async () => [...document.querySelectorAll("button")].find(b => b.textContent === "Voir les liens courants")!.click());
  for (let n = 0; n < 200 && document.querySelector('[role="status"]'); n++) await act(async () => { await new Promise(r => setTimeout(r, 10)); });
}
const component = () => <MarketingCurrentConversions institute={v.institute_id} campaign={v.campaign_id} period={v.window} />;
test("explicit current catalog independently verifies current pointer and full sources before selection", async () => {
  sessionStorage.clear(); setAccessToken(token()); const root = createRoot(document.getElementById("root")!);
  let reads = 0, corrupt = false;
  globalThis.fetch = async url => {
    reads++; const path = String(url);
    if (path.includes("/conversions/current?")) return reply(v.page);
    if (path.endsWith("/current")) return reply(v.linked);
    if (path.includes("/conversions/")) return reply(v.linked);
    if (path.includes("/campaigns/")) return reply(a.authorization);
    if (path.includes("/outcomes/")) return reply(a.accepted);
    return reply(corrupt ? { ...a.intent, request_fingerprint: "0".repeat(64) } : a.intent);
  };
  try {
    await act(async () => root.render(component())); assert.equal(reads, 0);
    await click(); assert.match(document.body.textContent!, /1 liens courants dans la période/);
    await act(async () => [...document.querySelectorAll("button")].find(b => b.textContent === `Ticket ${a.ticket.ticket_id} · Test`)!.click());
    assert.ok(document.querySelector('[aria-label="Historique des conversions"]'));
    assert.ok(document.querySelector('[aria-label="Enregistrer une conversion"]'));
    corrupt = true; await click(); assert.ok(document.querySelector('[role="alert"]'));
    assert.doesNotMatch(document.body.textContent!, /1 liens courants/);
    assert.equal(document.querySelector('[aria-label="Enregistrer une conversion"]'), null);
    setAccessToken(token("accueil")); await act(async () => root.render(component()));
    assert.equal(document.querySelector("button"), null);
  } finally { await act(async () => root.unmount()); }
});
test("retracted current pointer or incomplete catalog cannot publish stale linked rows", async () => {
  sessionStorage.clear(); setAccessToken(token()); const root = createRoot(document.getElementById("root")!);
  let incomplete = false;
  globalThis.fetch = async url => {
    const path = String(url);
    if (path.includes("/conversions/current?")) return reply(incomplete ? { ...v.page, total: 25 } : v.page);
    if (path.endsWith("/current")) return reply(v.retracted);
    if (path.includes("/conversions/")) return reply(v.linked);
    if (path.includes("/campaigns/")) return reply(a.authorization);
    if (path.includes("/outcomes/")) return reply(a.accepted);
    return reply(a.intent);
  };
  try {
    await act(async () => root.render(component())); await click();
    assert.ok(document.querySelector('[role="alert"]')); assert.doesNotMatch(document.body.textContent!, /1 liens courants/);
    incomplete = true; await click(); assert.ok(document.querySelector('[role="alert"]'));
  } finally { await act(async () => root.unmount()); }
});
