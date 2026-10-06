import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import React, { act } from "react";
import { PaymentHistory } from "../src/components/PaymentHistory";
import { setAccessToken } from "../src/api/session";
const dom = new JSDOM("<!doctype html><div id='root'></div>", { url: "http://localhost:5173" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const response = (value: unknown) => new Response(JSON.stringify(value), { headers: { "Content-Type": "application/json" } });
const facts = (ticket: string, amount = "10.35") => ({ ticket_id: ticket, protected: true, operations: [{ id: "operation", kind: "authorize", amount, currency: "CHF", status: "unknown", applied: false, active_protection: true, loyalty_decision: null }] });

test("payment history displays unknown protection and hides stale facts after read failure", async () => {
  const root = createRoot(document.getElementById("root")!);
  const original = globalThis.fetch;
  setAccessToken("session");
  let reads = 0;
  globalThis.fetch = async () => ++reads === 1 ? response(facts("ticket")) : response(facts("wrong-ticket"));
  try {
    await act(async () => root.render(<PaymentHistory instituteId="inst" ticketId="ticket" />));
    assert.match(document.body.textContent!, /10,35 CHF/);
    assert.match(document.body.textContent!, /ticket reste protégé/);
    await act(async () => document.querySelector<HTMLButtonElement>("button")!.click());
    assert.match(document.body.textContent!, /Lecture des paiements incomplète/);
    assert.doesNotMatch(document.body.textContent!, /10,35 CHF/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = original; setAccessToken(null); }
});

test("late old ticket/session response cannot overwrite current payment history", async () => {
  const root = createRoot(document.getElementById("root")!);
  const original = globalThis.fetch;
  setAccessToken("old-session");
  let resolveOld!: (value: Response) => void;
  globalThis.fetch = async input => String(input).includes("/old/snapshot") ? new Promise<Response>(resolve => { resolveOld = resolve; }) : response(facts("new", "20.50"));
  try {
    await act(async () => root.render(<PaymentHistory instituteId="inst" ticketId="old" />));
    setAccessToken("new-session");
    await act(async () => root.render(<PaymentHistory instituteId="inst" ticketId="new" />));
    await act(async () => resolveOld(response(facts("old", "99.99"))));
    assert.match(document.body.textContent!, /20,50 CHF/);
    assert.doesNotMatch(document.body.textContent!, /99,99 CHF/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = original; setAccessToken(null); }
});

test("unexecuted prepared history allows a current authorization quote while unknown protection hides it", async () => {
  const root = createRoot(document.getElementById("root")!), original = globalThis.fetch;
  setAccessToken(`h.${Buffer.from(JSON.stringify({ sub: "operator", role: "accueil" })).toString("base64url")}.s`);
  let protectedPayment = false, quoteReads = 0;
  globalThis.fetch = async (url, options) => {
    assert.equal(options?.method, "GET");
    if (String(url).endsWith("authorization-quote")) {
      quoteReads++;
      return response({ ticket_id: "ticket", amount: "11.35", currency: "CHF" });
    }
    const snapshot = facts("ticket");
    return response({ ...snapshot, protected: protectedPayment, operations: snapshot.operations.map(row => ({ ...row, status: protectedPayment ? "unknown" : "prepared", active_protection: protectedPayment })) });
  };
  try {
    await act(async () => root.render(<PaymentHistory instituteId="inst" ticketId="ticket" authorizationEligible onRefresh={async () => true} />));
    assert.match(document.body.textContent!, /11,35 CHF/);
    assert.equal(quoteReads, 1);
    protectedPayment = true;
    await act(async () => document.querySelector<HTMLButtonElement>("button")!.click());
    assert.doesNotMatch(document.body.textContent!, /11,35 CHF/);
    assert.equal(quoteReads, 1);
  } finally { await act(async () => root.unmount()); globalThis.fetch = original; setAccessToken(null); }
});
