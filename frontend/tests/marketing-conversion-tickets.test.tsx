import test from "node:test";
import assert from "node:assert/strict";
import React, { act } from "react";
import { JSDOM } from "jsdom";
import { readFileSync } from "node:fs";
import { MarketingConversionTickets } from "../src/components/MarketingConversionTickets";
import { validConversionTicketRead } from "../src/marketing-conversion-utils";
import { setAccessToken } from "../src/api/session";
const v = JSON.parse(readFileSync(new URL("./fixtures/marketing-conversions-13bb.json", import.meta.url), "utf8"));
const intent = v.linked.attribution.intent, accepted = v.linked.attribution.accepted, institute = v.institute_id;
test("actual authoritative four-ticket export matches scope, window, capture and precise billing diagnostics", async () => {
  assert.equal(await validConversionTicketRead(v.tickets, institute, intent, accepted, v.tickets.request, 0, 20), true);
  for (const patch of [{ customer_id: "foreign" }, { amount_minor: "01" }, { captured_at: "2026-10-12T12:00:00Z" },
    { closed_at: v.tickets.window.end }, { currency: "USD" }]) {
    const bad = structuredClone(v.tickets); Object.assign(bad.page.items[0], patch);
    assert.equal(await validConversionTicketRead(bad, institute, intent, accepted, v.tickets.request, 0, 20), false);
  }
  for (const patch of [{ total: 5 }, { offset: 1 }, { limit: 51 }, { items: [...v.tickets.page.items].reverse() }])
    assert.equal(await validConversionTicketRead({ ...v.tickets, page: { ...v.tickets.page, ...patch } }, institute, intent, accepted, v.tickets.request, 0, 20), false);
  assert.equal(await validConversionTicketRead(v.tickets, "foreign", intent, accepted, v.tickets.request, 0, 20), false);
  assert.equal(await validConversionTicketRead(v.tickets, institute, intent, accepted, { ...v.tickets.request, expected_fingerprint: "0".repeat(64) }, 0, 20), false);
});
const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (role = "responsable_institut") => `h.${Buffer.from(JSON.stringify({ sub: "manager", role })).toString("base64url")}.s`;
const reply = (value: unknown) => new Response(JSON.stringify(value), { headers: { "Content-Type": "application/json" } });
async function input(index: number, value: string) {
  await act(async () => {
    const element = document.querySelectorAll("input")[index];
    Object.getOwnPropertyDescriptor(dom.window.HTMLInputElement.prototype, "value")!.set!.call(element, value);
    element.dispatchEvent(new dom.window.Event("input", { bubbles: true }));
    element.dispatchEvent(new dom.window.Event("change", { bubbles: true }));
  });
}
async function click(label: string) {
  const button = [...document.querySelectorAll("button")].find(b => b.textContent === label)!;
  await act(async () => button.click());
  for (let n = 0; n < 100 && document.querySelector('[role="status"]'); n++)
    await act(async () => { await new Promise(resolve => setTimeout(resolve, 10)); });
}
test("explicit native source rereads expose paid diagnostics, select without POST and refuse substituted sources", async () => {
  setAccessToken(token()); const root = createRoot(document.getElementById("root")!);
  let catalogs = 0, calls = 0, corruptSource = false;
  globalThis.fetch = async (url, init) => {
    assert.ok(!init?.method || init.method === "GET"); calls++;
    const path = String(url);
    if (path.includes("conversion-tickets?")) {
      catalogs++; const q = new URL(path, "http://localhost").searchParams, r = structuredClone(v.tickets);
      assert.equal(q.get("start"), accepted.request.result.observed_at);
      r.request.start = r.window.start = q.get("start"); r.request.end = r.window.end = q.get("end");
      return reply(r);
    }
    if (path.includes("/outcomes/")) return reply(accepted);
    return reply(corruptSource ? { ...intent, request_fingerprint: "0".repeat(64) } : intent);
  };
  try {
    await act(async () => root.render(<MarketingConversionTickets institute={institute} intent={intent} accepted={accepted} timezone="Europe/Zurich" />));
    assert.equal(calls, 0); await click("Lire les tickets payés"); assert.equal(calls, 0);
    await input(0, "2026-10-07"); await input(1, "2026-10-10"); await click("Lire les tickets payés");
    assert.equal(catalogs, 1); assert.match(document.body.textContent!, /4 tickets payés/);
    assert.match(document.body.textContent!, /Montant manquant/); assert.match(document.body.textContent!, /Montant invalide/);
    assert.match(document.body.textContent!, /Devise inconnue/); assert.match(document.body.textContent!, /123\.45/);
    const ticket = [...document.querySelectorAll("button")].find(b => b.textContent?.includes("Ticket linked-paid"))!;
    await act(async () => ticket.click()); assert.match(document.body.textContent!, /Aucun lien de conversion enregistré/);
    corruptSource = true; await click("Lire les tickets payés");
    assert.equal(catalogs, 1); assert.ok(document.querySelector('[role="alert"]'));
    assert.doesNotMatch(document.body.textContent!, /Ticket sélectionné/);
    corruptSource = false; await click("Lire les tickets payés");
    const staleTicket = [...document.querySelectorAll("button")].find(b => b.textContent?.includes("Ticket linked-paid"))!;
    setAccessToken(token("accueil"));
    await act(async () => staleTicket.click());
    assert.doesNotMatch(document.body.textContent!, /Ticket sélectionné/);
    await act(async () => root.render(<MarketingConversionTickets institute={institute} intent={intent} accepted={accepted} timezone="Europe/Zurich" />));
    assert.equal(document.querySelector("button"), null);
  } finally { await act(async () => root.unmount()); }
});
