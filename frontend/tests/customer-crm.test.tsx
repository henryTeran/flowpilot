import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import React, { act } from "react";
import { CustomerCrmProfile, crmMoney } from "../src/components/CustomerCrmPanel";
import { setAccessToken } from "../src/api/session";
import { crmProfile, crmEmptyReturn } from "./crm-fixture";
const dom = new JSDOM("<!doctype html><div id='root'></div>", { url: "http://localhost:5173" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (actor = "manager", role = "responsable_institut") => `h.${Buffer.from(JSON.stringify({ role, sub: actor })).toString("base64url")}.s`;
const customer = { id: "customer_a", institute_id: "i", display_name: "Alice", phone: null, created_at: "2026-10-06T23:59:59.999950Z" };
const reply = (v: unknown) => new Response(JSON.stringify(v), { headers: { "Content-Type": "application/json" } });
test("native CRM profile isolates role/customer/actor and hides forged fresh readings", async () => {
  const fetch = globalThis.fetch, root = createRoot(document.getElementById("root")!), pending: ((v: Response) => void)[] = [];
  globalThis.fetch = async url => String(url).includes("/return-cycle?") ? reply(crmEmptyReturn()) : new Promise(resolve => pending.push(resolve));
  try {
    setAccessToken(token("manager", "accueil")); await act(async () => root.render(<CustomerCrmProfile institute="i" customer={customer} />));
    assert.equal(pending.length, 0);
    setAccessToken(token()); await act(async () => root.render(<CustomerCrmProfile institute="i" customer={customer} />));
    setAccessToken(token("new")); await act(async () => root.render(<CustomerCrmProfile institute="i" customer={customer} />));
    await act(async () => pending[0](reply(crmProfile()))); assert.doesNotMatch(document.body.textContent!, /Nouvelle cliente/);
    await act(async () => pending[1](reply(crmProfile()))); assert.match(document.body.textContent!, /Nouvelle cliente/);
    await act(async () => document.querySelector<HTMLButtonElement>("button")!.click()); assert.doesNotMatch(document.body.textContent!, /Nouvelle cliente/);
    const forged = crmProfile(); forged.segment!.state = "VIP";
    await act(async () => pending[2](reply(forged))); assert.match(document.body.textContent!, /à vérifier/);
    await act(async () => root.render(<CustomerCrmProfile institute="i" customer={{ ...customer, id: "customer_b" }} />));
    await act(async () => pending[3](reply(crmProfile()))); assert.match(document.body.textContent!, /à vérifier/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = fetch; }
});
test("native profile preserves unavailable policy explanation and exact large money", async () => {
  const fetch = globalThis.fetch, root = createRoot(document.getElementById("root")!);
  const r = crmProfile(); r.policy_original = null; r.segment = null; r.unavailable_reason = "policy_absent";
  globalThis.fetch = async () => reply(r);
  try {
    setAccessToken(token()); await act(async () => root.render(<CustomerCrmProfile institute="i" customer={customer} />));
    assert.match(document.body.textContent!, /non configurée/); assert.match(document.body.textContent!, /valeur future restent inconnus/);
    assert.equal(crmMoney("9007199254740993", "CHF"), "90071992547409,93 CHF");
  } finally { await act(async () => root.unmount()); globalThis.fetch = fetch; }
});
