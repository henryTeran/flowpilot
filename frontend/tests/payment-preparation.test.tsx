import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import React, { act } from "react";
import { PaymentPreparation } from "../src/components/PaymentPreparation";
import { setAccessToken } from "../src/api/session";
const dom = new JSDOM("<!doctype html><div id='root'></div>", { url: "http://localhost:5173" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const response = (value: unknown) => new Response(JSON.stringify(value), { headers: { "Content-Type": "application/json" } });
const token = (role = "responsable_institut") => `h.${Buffer.from(JSON.stringify({ sub: "actor", role })).toString("base64url")}.s`;
const parent = { id: "parent", amount: "10.35", currency: "CHF" };

for (const kind of ["capture", "cancel", "refund"] as const) test(`${kind} preparation replays the original key after a lost response`, async () => {
  sessionStorage.clear(); setAccessToken(token());
  let root = createRoot(document.getElementById("root")!);
  const original = globalThis.fetch, key = `flowpilot.payment-preparation:${JSON.stringify(["inst", "ticket", "parent", kind, "actor"])}`;
  const row = { kind, amount: kind === "refund" ? "5.00" : parent.amount, currency: "CHF", parent_intent_id: "parent", idempotency_key: "saved-key" };
  sessionStorage.setItem(key, JSON.stringify(row));
  let posts = 0, recorded = 0;
  globalThis.fetch = async (url, options) => {
    if (options?.method === "POST") {
      assert.match(String(url), /\/tickets\/ticket\/intents$/);
      assert.deepEqual(JSON.parse(String(options.body)), row);
      assert.deepEqual(JSON.parse(sessionStorage.getItem(key)!), row);
      if (++posts === 1) throw new Error("Lost reply");
      return response({ ...row, id: "original" });
    }
    return response({ ticket_id: "ticket", operations: [{ ...row, id: "original", actor_id: "actor" }] });
  };
  const props = { instituteId: "inst", ticketId: "ticket", parent, kind, onRefresh: async () => true, onRecorded: () => { recorded++; } };
  try {
    await act(async () => root.render(<PaymentPreparation {...props} />));
    await act(async () => document.querySelector<HTMLButtonElement>("button")!.click());
    assert.equal(recorded, 0); assert.ok(sessionStorage.getItem(key));
    await act(async () => root.unmount()); root = createRoot(document.getElementById("root")!);
    await act(async () => root.render(<PaymentPreparation {...props} />));
    await act(async () => document.querySelector<HTMLButtonElement>("button")!.click());
    assert.equal(recorded, 1); assert.equal(posts, 2); assert.equal(sessionStorage.getItem(key), null);
  } finally { await act(async () => root.unmount()); globalThis.fetch = original; sessionStorage.clear(); }
});

test("new capture preparation saves a key before POST and rejects changed response value", async () => {
  sessionStorage.clear(); setAccessToken(token());
  const root = createRoot(document.getElementById("root")!), original = globalThis.fetch;
  let reads = 0;
  globalThis.fetch = async (_url, options) => {
    if (options?.method !== "POST") reads++;
    const body = JSON.parse(String(options?.body));
    const key = `flowpilot.payment-preparation:${JSON.stringify(["inst", "ticket", "parent", "capture", "actor"])}`;
    assert.deepEqual(JSON.parse(sessionStorage.getItem(key)!), body);
    assert.ok(body.idempotency_key); assert.equal(body.parent_intent_id, "parent");
    return response({ ...body, id: "original", amount: "99.00" });
  };
  try {
    await act(async () => root.render(<PaymentPreparation instituteId="inst" ticketId="ticket" parent={parent} kind="capture" onRefresh={async () => { assert.fail("Changed value refreshed"); return true; }} onRecorded={() => assert.fail("Changed value recorded")} />));
    await act(async () => document.querySelector<HTMLButtonElement>("button")!.click());
    assert.equal(reads, 0); assert.match(document.body.textContent!, /vérifier/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = original; sessionStorage.clear(); }
});

test("refund preparation stays hidden from cashier role", async () => {
  sessionStorage.clear(); setAccessToken(token("accueil"));
  const root = createRoot(document.getElementById("root")!);
  try {
    await act(async () => root.render(<PaymentPreparation instituteId="inst" ticketId="ticket" parent={parent} kind="refund" onRefresh={async () => true} onRecorded={() => {}} />));
    assert.equal(document.querySelector("button"), null);
  } finally { await act(async () => root.unmount()); sessionStorage.clear(); }
});
