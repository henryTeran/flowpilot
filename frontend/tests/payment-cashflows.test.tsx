import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import React, { act } from "react";
import { PaymentCashflows } from "../src/components/PaymentCashflows";
import { setAccessToken } from "../src/api/session";
const dom = new JSDOM("<!doctype html><div id='root'></div>", { url: "http://localhost:5173" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (subject: string, role = "responsable_institut") => `h.${Buffer.from(JSON.stringify({ sub: subject, role })).toString("base64url")}.s`;
const response = (value: unknown) => new Response(JSON.stringify(value), { headers: { "Content-Type": "application/json" } });
const account = (currency = "CHF", account_id = "account", captured = "10.35") => ({ provider: "provider", account_id, currency, captured, applied: captured, unapplied: "0.00", refunded: "3.00", refund_reserved: "2.00", net_confirmed: "7.35" });
const facts = (institute_id = "inst", accounts = [account()]) => ({ institute_id, accounts });

test("cashflows are manager-only and never request an empty institute", async () => {
  const root = createRoot(document.getElementById("root")!), original = globalThis.fetch;
  let reads = 0;
  globalThis.fetch = async () => { reads++; return response(facts()); };
  try {
    setAccessToken(token("cashier", "accueil"));
    await act(async () => root.render(<PaymentCashflows instituteId="inst" />));
    assert.equal(reads, 0);
    assert.equal(document.body.textContent, "");
    setAccessToken(token("manager"));
    await act(async () => root.render(<PaymentCashflows instituteId="" />));
    assert.equal(reads, 0);
  } finally { await act(async () => root.unmount()); globalThis.fetch = original; setAccessToken(null); }
});

test("cashflows preserve recorded cents and separate accounts/currencies; invalid refresh hides cached facts", async () => {
  const root = createRoot(document.getElementById("root")!), original = globalThis.fetch;
  setAccessToken(token("manager"));
  let invalid = false;
  globalThis.fetch = async (url, options) => {
    assert.match(String(url), /\/payments\/institutes\/inst\/cashflows$/);
    assert.equal(options?.method, "GET");
    return response(invalid ? facts("foreign") : facts("inst", [account(), account("EUR", "second", "90071992547409.93")]));
  };
  try {
    await act(async () => root.render(<PaymentCashflows instituteId="inst" />));
    assert.equal(document.querySelectorAll("h4").length, 2);
    assert.match(document.body.textContent!, /10,35 CHF/);
    assert.match(document.body.textContent!, /90071992547409,93 EUR/);
    assert.match(document.body.textContent!, /Remboursements réservés2,00 CHF/);
    invalid = true;
    await act(async () => document.querySelector<HTMLButtonElement>("button")!.click());
    assert.match(document.body.textContent!, /Lecture des flux de paiement incomplète/);
    assert.doesNotMatch(document.body.textContent!, /10,35|90071992547409/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = original; setAccessToken(null); }
});

test("late old institute and token reads cannot publish current cashflows", async () => {
  const root = createRoot(document.getElementById("root")!), original = globalThis.fetch;
  let resolveOld!: (value: Response) => void;
  globalThis.fetch = async url => String(url).includes("/old/") ? new Promise(resolve => { resolveOld = resolve; }) : response(facts("new", [account("EUR", "new-account", "20.50")]));
  try {
    setAccessToken(token("old-manager"));
    await act(async () => root.render(<PaymentCashflows instituteId="old" />));
    setAccessToken(token("new-manager"));
    await act(async () => root.render(<PaymentCashflows instituteId="new" />));
    await act(async () => resolveOld(response(facts("old", [account("CHF", "old-account", "99.99")]))));
    assert.match(document.body.textContent!, /20,50 EUR/);
    assert.doesNotMatch(document.body.textContent!, /99,99|old-account/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = original; setAccessToken(null); }
});
