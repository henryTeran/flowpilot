import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import React, { act } from "react";
import { RefundLoyaltyDecision } from "../src/components/RefundLoyaltyDecision";
import { PaymentHistory } from "../src/components/PaymentHistory";
import { setAccessToken } from "../src/api/session";
const dom = new JSDOM("<!doctype html><div id='root'></div>", { url: "http://localhost:5173" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const response = (value: unknown) => new Response(JSON.stringify(value), { headers: { "Content-Type": "application/json" } });
const token = (actor: string, role = "responsable_institut") => `header.${Buffer.from(JSON.stringify({ sub: actor, role })).toString("base64url")}.signature`;
const key = (actor = "manager") => `flowpilot.refund-loyalty:${JSON.stringify(["inst", "ticket", "refund", actor])}`;
const intent = { points: -5, reason: "Refund correction", idempotency_key: "original-key" };
const receipt = (row = intent) => ({ ...row, id: "decision", refund_intent_id: "refund", actor_id: "manager", entry_id: row.points === 0 ? null : "entry" });

test("new explicit retention saves its immutable intention before POST and verifies the receipt", async () => {
  sessionStorage.clear(); setAccessToken(token("manager"));
  const root = createRoot(document.getElementById("root")!), original = globalThis.fetch;
  let posted: typeof intent | undefined, completed = 0;
  globalThis.fetch = async (_url, options) => {
    if (options?.method === "POST") {
      posted = JSON.parse(String(options.body));
      assert.deepEqual(JSON.parse(sessionStorage.getItem(key())!), posted);
      assert.equal(posted!.points, 0); assert.equal(posted!.reason, "Retain original points");
      assert.ok(posted!.idempotency_key); return response(receipt(posted));
    }
    return response(posted ? receipt(posted) : null);
  };
  try {
    await act(async () => root.render(<RefundLoyaltyDecision instituteId="inst" ticketId="ticket" refundId="refund" onRefresh={async () => true} onRecorded={() => { completed++; }} />));
    const fields = document.querySelectorAll<HTMLInputElement>("input");
    await act(async () => {
      Object.getOwnPropertyDescriptor(dom.window.HTMLInputElement.prototype, "value")!.set!.call(fields[1], "Retain original points");
      fields[1].dispatchEvent(new dom.window.Event("input", { bubbles: true }));
    });
    assert.equal(document.querySelector<HTMLButtonElement>("button")!.disabled, false);
    await act(async () => document.querySelector<HTMLButtonElement>("button")!.click());
    assert.equal(completed, 1); assert.equal(sessionStorage.getItem(key()), null);
  } finally { await act(async () => root.unmount()); globalThis.fetch = original; sessionStorage.clear(); }
});

test("lost POST response recovers the original receipt after remount without another debit request", async () => {
  sessionStorage.clear(); setAccessToken(token("manager")); sessionStorage.setItem(key(), JSON.stringify(intent));
  let root = createRoot(document.getElementById("root")!);
  const original = globalThis.fetch;
  let committed = false, posts = 0, refreshed = 0, recorded = 0;
  globalThis.fetch = async (_url, options) => {
    if (options?.method === "POST") {
      posts++; assert.deepEqual(JSON.parse(String(options.body)), intent);
      assert.deepEqual(JSON.parse(sessionStorage.getItem(key())!), intent);
      committed = true; throw new Error("Lost response");
    }
    return response(committed ? receipt() : null);
  };
  const props = { instituteId: "inst", ticketId: "ticket", refundId: "refund", onRefresh: async () => { refreshed++; return true; }, onRecorded: () => { recorded++; } };
  try {
    await act(async () => root.render(<RefundLoyaltyDecision {...props} />));
    await act(async () => document.querySelector<HTMLButtonElement>("button")!.click());
    assert.match(document.body.textContent!, /Lost response/); assert.ok(sessionStorage.getItem(key()));
    await act(async () => root.unmount()); root = createRoot(document.getElementById("root")!);
    await act(async () => root.render(<RefundLoyaltyDecision {...props} />));
    await act(async () => document.querySelector<HTMLButtonElement>("button")!.click());
    assert.equal(posts, 1); assert.equal(refreshed, 1); assert.equal(recorded, 1); assert.equal(sessionStorage.getItem(key()), null);
  } finally { await act(async () => root.unmount()); globalThis.fetch = original; sessionStorage.clear(); }
});

test("another decision key cannot confirm an original intention with identical visible terms", async () => {
  sessionStorage.clear(); setAccessToken(token("manager")); sessionStorage.setItem(key(), JSON.stringify(intent));
  const root = createRoot(document.getElementById("root")!), original = globalThis.fetch;
  let posts = 0, refreshes = 0;
  globalThis.fetch = async (_url, options) => { if (options?.method === "POST") posts++; return response(receipt({ ...intent, idempotency_key: "other-key" })); };
  try {
    await act(async () => root.render(<RefundLoyaltyDecision instituteId="inst" ticketId="ticket" refundId="refund" onRefresh={async () => { refreshes++; return true; }} onRecorded={() => assert.fail("Wrong receipt accepted")} />));
    await act(async () => document.querySelector<HTMLButtonElement>("button")!.click());
    assert.match(document.body.textContent!, /ne correspond pas/); assert.equal(posts, 0); assert.equal(refreshes, 0); assert.ok(sessionStorage.getItem(key()));
  } finally { await act(async () => root.unmount()); globalThis.fetch = original; sessionStorage.clear(); }
});

test("late old-session recovery cannot post, refresh or remove the persisted intention", async () => {
  sessionStorage.clear(); setAccessToken(token("manager")); sessionStorage.setItem(key(), JSON.stringify(intent));
  const root = createRoot(document.getElementById("root")!), original = globalThis.fetch;
  let resolve!: (value: Response) => void, posts = 0;
  globalThis.fetch = async (_url, options) => { if (options?.method === "POST") posts++; return new Promise<Response>(done => { resolve = done; }); };
  try {
    await act(async () => root.render(<RefundLoyaltyDecision instituteId="inst" ticketId="ticket" refundId="refund" onRefresh={async () => { assert.fail("Old session refreshed"); return true; }} onRecorded={() => assert.fail("Old session completed")} />));
    await act(async () => document.querySelector<HTMLButtonElement>("button")!.click());
    setAccessToken(token("other"));
    await act(async () => resolve(response(null)));
    assert.equal(posts, 0); assert.ok(sessionStorage.getItem(key()));
  } finally { await act(async () => root.unmount()); globalThis.fetch = original; sessionStorage.clear(); }
});

test("explicit zero retention waits for successful data refresh before clearing recovery", async () => {
  const keep = { ...intent, points: 0 };
  sessionStorage.clear(); setAccessToken(token("manager")); sessionStorage.setItem(key(), JSON.stringify(keep));
  const root = createRoot(document.getElementById("root")!), original = globalThis.fetch;
  let fresh = false, recorded = 0;
  globalThis.fetch = async () => response(receipt(keep));
  try {
    await act(async () => root.render(<RefundLoyaltyDecision instituteId="inst" ticketId="ticket" refundId="refund" onRefresh={async () => fresh} onRecorded={() => { recorded++; }} />));
    await act(async () => document.querySelector<HTMLButtonElement>("button")!.click());
    assert.ok(sessionStorage.getItem(key())); assert.equal(recorded, 0);
    fresh = true;
    await act(async () => document.querySelector<HTMLButtonElement>("button")!.click());
    assert.equal(sessionStorage.getItem(key()), null); assert.equal(recorded, 1);
  } finally { await act(async () => root.unmount()); globalThis.fetch = original; sessionStorage.clear(); }
});

test("cashier history stays read-only and manager editing is limited to confirmed undecided refunds", async () => {
  sessionStorage.clear(); setAccessToken(token("manager", "accueil"));
  const root = createRoot(document.getElementById("root")!), original = globalThis.fetch;
  const operation = { id: "refund", kind: "refund", amount: "10.35", currency: "CHF", status: "refunded", applied: false, active_protection: false, loyalty_decision: null };
  let status = "refunded";
  globalThis.fetch = async () => response({ ticket_id: "ticket", protected: false, operations: [{ ...operation, status }] });
  try {
    const render = () => root.render(<PaymentHistory instituteId="inst" ticketId="ticket" onRefresh={async () => true} />);
    await act(async () => render());
    assert.equal(document.querySelectorAll("input").length, 0);
    setAccessToken(token("manager"));
    await act(async () => render());
    assert.equal(document.querySelectorAll("input").length, 2);
    status = "pending";
    await act(async () => document.querySelector<HTMLButtonElement>("button")!.click());
    assert.equal(document.querySelectorAll("input").length, 0);
  } finally { await act(async () => root.unmount()); globalThis.fetch = original; sessionStorage.clear(); }
});

test("a definitive POST rejection permits a corrected decision without retaining an uncertain debit", async () => {
  sessionStorage.clear(); setAccessToken(token("manager")); sessionStorage.setItem(key(), JSON.stringify(intent));
  const root = createRoot(document.getElementById("root")!), original = globalThis.fetch;
  globalThis.fetch = async (_url, options) => options?.method === "POST"
    ? new Response(JSON.stringify({ detail: "Insufficient points" }), { status: 400, headers: { "Content-Type": "application/json" } }) : response(null);
  try {
    await act(async () => root.render(<RefundLoyaltyDecision instituteId="inst" ticketId="ticket" refundId="refund" onRefresh={async () => { assert.fail("Rejected decision refreshed"); return true; }} onRecorded={() => assert.fail("Rejected decision recorded")} />));
    await act(async () => document.querySelector<HTMLButtonElement>("button")!.click());
    assert.equal(sessionStorage.getItem(key()), null);
    assert.equal(document.querySelectorAll("input").length, 2);
    assert.match(document.body.textContent!, /Insufficient points/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = original; sessionStorage.clear(); }
});
