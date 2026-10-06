import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import React, { act } from "react";
import { PaymentRecovery } from "../src/components/PaymentRecovery";
import { setAccessToken } from "../src/api/session";
const dom = new JSDOM("<!doctype html><div id='root'></div>", { url: "http://localhost:5173" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (sub = "operator", role = "accueil") => `h.${Buffer.from(JSON.stringify({ sub, role })).toString("base64url")}.s`;
const response = (value: unknown) => new Response(JSON.stringify(value), { headers: { "Content-Type": "application/json" } });
const operation = { id: "original", kind: "authorize", amount: "10.35", currency: "CHF", actor_id: "operator", status: "unknown" };

test("lost dispatch response retries only the original operation and confirms stored facts before refresh", async () => {
  setAccessToken(token()); const root = createRoot(document.getElementById("root")!), original = globalThis.fetch;
  let posts = 0, refreshed = 0, recorded = 0;
  globalThis.fetch = async (url, options) => {
    if (options?.method === "POST") {
      assert.match(String(url), /\/intents\/original\/dispatch$/); assert.equal(options.body, undefined);
      if (++posts === 1) throw new Error("Lost response");
      return response({ ...operation, status: "authorized" });
    }
    return response({ ticket_id: "ticket", operations: [{ ...operation, status: "authorized" }] });
  };
  try {
    await act(async () => root.render(<PaymentRecovery instituteId="inst" ticketId="ticket" operation={operation} onRefresh={async () => { refreshed++; return true; }} onRecorded={() => { recorded++; }} />));
    await act(async () => document.querySelector<HTMLButtonElement>("button")!.click());
    assert.equal(refreshed, 0); assert.match(document.body.textContent!, /Lost response/);
    await act(async () => document.querySelector<HTMLButtonElement>("button")!.click());
    assert.equal(posts, 2); assert.equal(refreshed, 1); assert.equal(recorded, 1);
  } finally { await act(async () => root.unmount()); globalThis.fetch = original; setAccessToken(null); }
});

test("wrong snapshot scope and late old-session responses cannot refresh or confirm recovery", async () => {
  setAccessToken(token()); const root = createRoot(document.getElementById("root")!), original = globalThis.fetch;
  let resolve!: (value: Response) => void, deferred = false;
  globalThis.fetch = async (_url, options) => options?.method === "POST"
    ? deferred ? new Promise<Response>(done => { resolve = done; }) : response({ ...operation, status: "authorized" })
    : response({ ticket_id: "foreign", operations: [{ ...operation, status: "authorized" }] });
  try {
    await act(async () => root.render(<PaymentRecovery instituteId="inst" ticketId="ticket" operation={operation} onRefresh={async () => { assert.fail("Invalid recovery refreshed"); return true; }} onRecorded={() => assert.fail("Invalid recovery confirmed")} />));
    await act(async () => document.querySelector<HTMLButtonElement>("button")!.click());
    assert.match(document.body.textContent!, /vérifier le résultat/);
    deferred = true;
    await act(async () => document.querySelector<HTMLButtonElement>("button")!.click());
    setAccessToken(token("other"));
    await act(async () => resolve(response({ ...operation, status: "authorized" })));
  } finally { await act(async () => root.unmount()); globalThis.fetch = original; setAccessToken(null); }
});

test("recovery is limited to original actors and managers for refunds", async () => {
  const root = createRoot(document.getElementById("root")!);
  try {
    for (const [sub, role, kind, status, visible] of [
      ["other", "accueil", "authorize", "unknown", false],
      ["operator", "accueil", "refund", "pending", false],
      ["operator", "responsable_institut", "refund", "pending", true],
      ["operator", "accueil", "authorize", "authorized", false],
    ] as const) {
      setAccessToken(token(sub, role));
      await act(async () => root.render(<PaymentRecovery instituteId="inst" ticketId="ticket" operation={{ ...operation, kind, status }} onRefresh={async () => true} onRecorded={() => {}} />));
      assert.equal(!!document.querySelector("button"), visible);
    }
  } finally { await act(async () => root.unmount()); setAccessToken(null); }
});
