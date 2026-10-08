import test from "node:test";
import assert from "node:assert/strict";
import React, { act } from "react";
import { JSDOM } from "jsdom";
import { readFileSync } from "node:fs";
import { RevenueSlotOpportunity } from "../src/components/RevenueSlotOpportunity";
import { setAccessToken } from "../src/api/session";
const fixture = JSON.parse(readFileSync(new URL("./fixtures/revenue-slot-14u.json",import.meta.url),"utf8"));
const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (role = "responsable_institut") => `h.${Buffer.from(JSON.stringify({ sub: "manager", role })).toString("base64url")}.s`;
const services = [{ id: "care", category_id: "category", name: "Soin explicite", duration_min: 20, status: "active", requires_machine: false, requires_appointment: false }];
const reply = (v: unknown) => new Response(JSON.stringify(v), { headers: { "Content-Type": "application/json" } });
async function choose(value: string) { await act(async () => { const el = document.querySelector("select")!; el.value = value; el.dispatchEvent(new dom.window.Event("change", { bubbles: true })); }); }
async function date(value: string) { await act(async () => { const el = document.querySelector("input")!; Object.getOwnPropertyDescriptor(dom.window.HTMLInputElement.prototype,"value")!.set!.call(el,value); el.dispatchEvent(new dom.window.Event("input", { bubbles: true })); el.dispatchEvent(new dom.window.Event("change", { bubbles: true })); }); }
async function click() { await act(async () => document.querySelector("button")!.click()); }
test("capacity review starts empty, binds institute-midnight horizon and masks invalid or unavailable projections", async () => {
  setAccessToken(token()); const root = createRoot(document.getElementById("root")!); let reads = 0, value: unknown = fixture;
  globalThis.fetch = async (url,init) => { reads++; assert.equal(init?.method,"GET"); const u = new URL(String(url),"http://localhost"); assert.equal(u.searchParams.get("service_id"),"care"); assert.equal(u.searchParams.get("horizon_end"),"2026-01-05T00:00:00.000Z"); return reply(value); };
  try { await act(async () => root.render(<RevenueSlotOpportunity institute="own" timezone="UTC" services={services} />)); assert.equal(reads,0); assert.equal(document.querySelector<HTMLSelectElement>("select")!.value,"");
    await click(); assert.equal(reads,0); await choose("care"); await date("2026-01-05"); await click(); assert.match(document.body.textContent!,/employee/); assert.match(document.body.textContent!,/20 min/); assert.match(document.body.textContent!,/1 tickets déjà/);
    assert.match(document.querySelector("article > p")!.textContent!, /02\.01\.2026/);
    value = { ...fixture, opportunity: { ...fixture.opportunity, capacity_reserved: true } }; await click(); assert.ok(document.querySelector('[role="alert"]')); assert.equal(document.querySelector("article"),null);
    value = { ...fixture, opportunity: null, unavailable_reason: "outside_horizon" }; await click(); assert.match(document.body.textContent!,/se termine après l’horizon/); assert.equal(document.querySelector("article"),null);
    value = fixture; await click(); assert.ok(document.querySelector("article")); await date("2026-01-06"); assert.equal(document.querySelector("article"),null);
  } finally { await act(async () => root.unmount()); }
});
test("catalog removal, replaced institute and removed authority invalidate late capacity reads", async () => {
  setAccessToken(token()); const root = createRoot(document.getElementById("root")!); let resolve!: (v: Response) => void, reads = 0;
  globalThis.fetch = async () => { reads++; return new Promise<Response>(r => { resolve = r; }); };
  try { await act(async () => root.render(<RevenueSlotOpportunity institute="own" timezone="UTC" services={services} />)); await choose("care"); await date("2026-01-05"); await click();
    await act(async () => root.render(<RevenueSlotOpportunity institute="own" timezone="UTC" services={[]} />)); await act(async () => resolve(reply(fixture))); assert.equal(document.querySelector("article"),null);
    await act(async () => root.render(<RevenueSlotOpportunity institute="own" timezone="UTC" services={services} />)); await click();
    await act(async () => root.render(<RevenueSlotOpportunity institute="new" timezone="UTC" services={services} />)); await act(async () => resolve(reply(fixture))); assert.equal(document.querySelector("article"),null); assert.equal(document.querySelector<HTMLInputElement>("input")!.value,"");
    setAccessToken(token("accueil")); await click(); assert.equal(reads,2); await act(async () => root.render(<RevenueSlotOpportunity institute="new" timezone="UTC" services={services} />)); assert.equal(document.querySelector("section"),null);
  } finally { await act(async () => root.unmount()); setAccessToken(token()); }
});
