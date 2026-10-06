import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import React, { act } from "react";
import { CapturedCheckout } from "../src/components/CapturedCheckout";
import { setAccessToken } from "../src/api/session";
const dom = new JSDOM("<!doctype html><div id='root'></div>", { url: "http://localhost:5173" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (sub = "operator") => `h.${Buffer.from(JSON.stringify({ sub, role: "accueil" })).toString("base64url")}.s`;
const response = (value: unknown) => new Response(JSON.stringify(value), { headers: { "Content-Type": "application/json" } });
const operation = { id: "capture", kind: "capture", amount: "10.35", currency: "CHF", actor_id: "operator", status: "captured", applied: false };
const key = `flowpilot.capture-checkout:${JSON.stringify(["inst", "ticket", "capture", "operator"])}`;

test("lost checkout response preserves original employee and method across remount", async () => {
  sessionStorage.clear(); setAccessToken(token());
  let root = createRoot(document.getElementById("root")!);
  const original = globalThis.fetch;
  let posts = 0, refreshed = 0, recorded = 0;
  globalThis.fetch = async (url, options) => {
    if (options?.method === "POST") {
      assert.match(String(url), /\/intents\/capture\/checkout$/);
      const body = JSON.parse(String(options.body));
      assert.deepEqual(body, { employee_id: "cashier-one", method: "cb" });
      assert.deepEqual(JSON.parse(sessionStorage.getItem(key)!), body);
      if (++posts === 1) throw new Error("Lost response");
      return response({ ticket_id: "ticket", status: "paid" });
    }
    return response({ ticket_id: "ticket", operations: [{ ...operation, applied: true }] });
  };
  const callbacks = { onRefresh: async () => { refreshed++; return true; }, onRecorded: () => { recorded++; } };
  try {
    await act(async () => root.render(<CapturedCheckout instituteId="inst" ticketId="ticket" operation={operation} employeeId="cashier-one" method="cb" {...callbacks} />));
    await act(async () => document.querySelector<HTMLButtonElement>("button")!.click());
    assert.ok(sessionStorage.getItem(key)); assert.equal(refreshed, 0);
    await act(async () => root.unmount()); root = createRoot(document.getElementById("root")!);
    await act(async () => root.render(<CapturedCheckout instituteId="inst" ticketId="ticket" operation={operation} employeeId="cashier-two" method="cheque" {...callbacks} />));
    await act(async () => document.querySelector<HTMLButtonElement>("button")!.click());
    assert.equal(posts, 2); assert.equal(refreshed, 1); assert.equal(recorded, 1); assert.equal(sessionStorage.getItem(key), null);
  } finally { await act(async () => root.unmount()); globalThis.fetch = original; sessionStorage.clear(); }
});

test("unapplied snapshot cannot confirm checkout and failed data refresh keeps original terms", async () => {
  sessionStorage.clear(); setAccessToken(token());
  const root = createRoot(document.getElementById("root")!), original = globalThis.fetch;
  let applied = false, refreshed = 0;
  globalThis.fetch = async (_url, options) => options?.method === "POST" ? response({ ticket_id: "ticket", status: "paid" })
    : response({ ticket_id: "ticket", operations: [{ ...operation, applied }] });
  try {
    await act(async () => root.render(<CapturedCheckout instituteId="inst" ticketId="ticket" operation={operation} employeeId="cashier" method="cb" onRefresh={async () => { refreshed++; return false; }} onRecorded={() => assert.fail("Unverified closure recorded")} />));
    await act(async () => document.querySelector<HTMLButtonElement>("button")!.click());
    assert.equal(refreshed, 0); assert.ok(sessionStorage.getItem(key));
    applied = true;
    await act(async () => document.querySelector<HTMLButtonElement>("button")!.click());
    assert.equal(refreshed, 1); assert.ok(sessionStorage.getItem(key));
  } finally { await act(async () => root.unmount()); globalThis.fetch = original; sessionStorage.clear(); }
});

test("late old-session closure cannot refresh or discard its recovery terms", async () => {
  sessionStorage.clear(); setAccessToken(token());
  const root = createRoot(document.getElementById("root")!), original = globalThis.fetch;
  let resolve!: (value: Response) => void, reads = 0;
  globalThis.fetch = async (_url, options) => {
    if (options?.method !== "POST") reads++;
    return new Promise<Response>(done => { resolve = done; });
  };
  try {
    await act(async () => root.render(<CapturedCheckout instituteId="inst" ticketId="ticket" operation={operation} employeeId="cashier" method="cb" onRefresh={async () => { assert.fail("Old session refreshed"); return true; }} onRecorded={() => assert.fail("Old session confirmed")} />));
    await act(async () => document.querySelector<HTMLButtonElement>("button")!.click());
    setAccessToken(token("other"));
    await act(async () => resolve(response({ ticket_id: "ticket", status: "paid" })));
    assert.equal(reads, 0); assert.ok(sessionStorage.getItem(key));
  } finally { await act(async () => root.unmount()); globalThis.fetch = original; sessionStorage.clear(); }
});
