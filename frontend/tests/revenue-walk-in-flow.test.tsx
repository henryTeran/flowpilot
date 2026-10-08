import test from "node:test";
import assert from "node:assert/strict";
import React, { act } from "react";
import { JSDOM } from "jsdom";
import { readFileSync } from "node:fs";
import { RevenueWalkInCancellations } from "../src/components/RevenueWalkInCancellations";
import { setAccessToken } from "../src/api/session";
const vector = JSON.parse(readFileSync(new URL("./fixtures/revenue-walk-in-14t.json", import.meta.url), "utf8"));
const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (role = "responsable_institut") => `h.${Buffer.from(JSON.stringify({ sub: "manager", role })).toString("base64url")}.s`;
async function input(el: HTMLInputElement, value: string) { await act(async () => { Object.getOwnPropertyDescriptor(dom.window.HTMLInputElement.prototype,"value")!.set!.call(el,value); el.dispatchEvent(new dom.window.Event("input", { bubbles: true })); el.dispatchEvent(new dom.window.Event("change", { bubbles: true })); }); }
async function click() { await act(async () => document.querySelector("button")!.click()); for (let n = 0; n < 250 && document.querySelector('[role="status"]'); n++) await act(async () => { await new Promise(r => setTimeout(r,20)); }); assert.equal(document.querySelector('[role="status"]'),null); }
const reply = (v: unknown) => new Response(JSON.stringify(v), { headers: { "Content-Type": "application/json" } });
test("explicit native reader hides prior facts on invalid reads/date edits and distinguishes zero, legacy and unknown currency", async () => {
  setAccessToken(token()); const root = createRoot(document.getElementById("root")!); let reads = 0, bad = false;
  globalThis.fetch = async (url,init) => { reads++; assert.equal(init?.method,"GET"); const u = new URL(String(url),"http://localhost"); assert.equal(u.searchParams.get("start"),"2026-01-01T00:00:00.000Z"); return reply(bad ? { ...vector, causal_loss_proven: true } : vector); };
  try { await act(async () => root.render(<RevenueWalkInCancellations institute="own" timezone="UTC" />)); assert.equal(reads,0);
    const dates = document.querySelectorAll<HTMLInputElement>("input"); await input(dates[0],"2026-01-01"); await input(dates[1],"2026-01-03"); await click();
    assert.match(document.body.textContent!, /0.00 CHF/); assert.match(document.body.textContent!, /12.34 EUR/); assert.match(document.body.textContent!, /ancienne sans preuve tarifaire/);
    assert.match(document.body.textContent!, /Devise inconnue/); const unknown = Array.from(document.querySelectorAll("article")).find(a => a.querySelector("h3")?.textContent === "Ticket annulé ticket-4")!;
    assert.doesNotMatch(unknown.textContent!, /5.00/); assert.match(document.body.textContent!, /Source 😀/);
    assert.match(document.body.textContent!, /2 unités/); assert.match(document.body.textContent!, /Retirée de la facture/);
    bad = true; await click(); assert.ok(document.querySelector('[role="alert"]')); assert.equal(document.querySelectorAll("article").length,0);
    bad = false; await click(); assert.ok(document.querySelector("article")); await input(dates[0],"2026-01-02"); assert.equal(document.querySelectorAll("article").length,0); assert.equal(reads,3);
  } finally { await act(async () => root.unmount()); }
});
test("late scoped responses and removed manager authority cannot revive proof or perform another request", async () => {
  setAccessToken(token()); const root = createRoot(document.getElementById("root")!); let resolve!: (r: Response) => void, reads = 0;
  globalThis.fetch = async () => { reads++; return new Promise<Response>(r => { resolve = r; }); };
  try { await act(async () => root.render(<RevenueWalkInCancellations institute="own" timezone="UTC" />)); const dates = document.querySelectorAll<HTMLInputElement>("input");
    await input(dates[0],"2026-01-01"); await input(dates[1],"2026-01-03"); await act(async () => document.querySelector("button")!.click());
    await act(async () => root.render(<RevenueWalkInCancellations institute="new" timezone="UTC" />)); await act(async () => resolve(reply(vector)));
    assert.equal(document.querySelectorAll("article").length,0); assert.equal(document.querySelector<HTMLInputElement>("input")!.value,"");
    setAccessToken(token("reception")); await act(async () => document.querySelector("button")!.click()); assert.equal(reads,1);
    await act(async () => root.render(<RevenueWalkInCancellations institute="new" timezone="UTC" />)); assert.equal(document.querySelector("section"),null);
  } finally { await act(async () => root.unmount()); setAccessToken(token()); }
});
