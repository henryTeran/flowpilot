import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import React, { act } from "react";
import { NewTicketWorkflow } from "../src/components/NewTicketWorkflow";
import { apiGet, apiPost } from "../src/api/client";
import { setAccessToken } from "../src/api/session";

const dom = new JSDOM("<!doctype html><div id='root'></div>", { url: "http://localhost:5173" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document,
  sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const category = { id: "cat", name: "Épilation", code: "EPILATION" };
const service = { id: "svc", category_id: "cat", name: "Aisselles", duration_min: 10,
  price_passage: 15, requires_machine: false, requires_appointment: false, status: "active" };

function button(text: string) {
  const element = [...document.querySelectorAll("button")].find((item) => item.textContent?.includes(text));
  assert.ok(element, `Missing button: ${text}`);
  return element;
}

test("anonymous arrival needs service selection and one submit; failed submission remains retryable", async () => {
  const root = createRoot(document.getElementById("root")!);
  let attempts = 0;
  let closed = false;
  const submitted: unknown[] = [];
  await act(async () => root.render(<NewTicketWorkflow open categories={[category]} services={[service]}
    onClose={() => { closed = true; }} onValidate={async (payload) => {
      submitted.push(payload);
      if (++attempts === 1) throw new Error("Temporary network failure");
    }} />));
  assert.equal(document.querySelector("input[placeholder='Nom']"), null);
  assert.equal(button("Ajouter à la file").disabled, true);
  await act(async () => button("Aisselles").click());
  assert.equal(button("Ajouter à la file").disabled, false);
  await act(async () => button("Ajouter à la file").click());
  assert.equal(closed, false);
  assert.ok(document.querySelector("[role='dialog']"));
  await act(async () => button("Ajouter à la file").click());
  assert.equal(closed, true);
  assert.deepEqual(submitted[0], submitted[1]);
  assert.deepEqual((submitted[0] as { customer: unknown }).customer, {
    lastName: "", firstName: "", phone: "", identificationMode: "passage_bm",
  });
  await act(async () => root.unmount());
});

test("HTTP integration carries the operator token and displays standardized business errors", async () => {
  const originalFetch = globalThis.fetch;
  const requests: Array<{ path: string; token: string | null }> = [];
  setAccessToken("operator-test-token");
  globalThis.fetch = async (url, init) => {
    requests.push({ path: String(url), token: new Headers(init?.headers).get("Authorization") });
    if (String(url).endsWith("/tickets")) return new Response(JSON.stringify({ error: {
      code: "http_400", message: "La collaboratrice a deja un ticket affecte",
    } }), { status: 400, headers: { "Content-Type": "application/json" } });
    return new Response("[]", { headers: { "Content-Type": "application/json" } });
  };
  try {
    await apiGet("/tickets/waiting?institute_id=demo");
    assert.equal(requests[0].token, "Bearer operator-test-token");
    await assert.rejects(apiPost("/tickets", {}), /La collaboratrice a deja un ticket affecte/);
    await apiPost("/auth/login", { email: "test@example.com", password: "test" });
    assert.equal(requests[2].token, null);
  } finally {
    setAccessToken(null);
    globalThis.fetch = originalFetch;
  }
});

test("operator login opens the app and logout clears the session", async () => {
  const { SessionGate } = await import("../src/components/SessionGate");
  const originalFetch = globalThis.fetch;
  let credentials: unknown;
  globalThis.fetch = async (url, init) => {
    if (String(url).endsWith("/auth/login")) {
      credentials = JSON.parse(String(init?.body));
      return new Response(JSON.stringify({ access_token: "operator-session", role: "accueil" }), {
        headers: { "Content-Type": "application/json" },
      });
    }
    return new Response("[]", { headers: { "Content-Type": "application/json" } });
  };
  const root = createRoot(document.getElementById("root")!);
  try {
    await act(async () => root.render(<SessionGate />));
    const setInput = (id: string, value: string) => {
      const input = document.getElementById(id)!;
      Object.getOwnPropertyDescriptor(dom.window.HTMLInputElement.prototype, "value")!.set!.call(input, value);
      input.dispatchEvent(new dom.window.Event("input", { bubbles: true }));
    };
    await act(async () => {
      setInput("flow-email", "operator@example.com");
      setInput("flow-password", "shift-password");
    });
    await act(async () => document.querySelector("form")!.dispatchEvent(new dom.window.Event("submit", { bubbles: true, cancelable: true })));
    assert.deepEqual(credentials, { email: "operator@example.com", password: "shift-password" });
    assert.equal(sessionStorage.getItem("flowpilot.access_token"), "operator-session");
    assert.ok(button("Déconnexion"));
    await act(async () => button("Déconnexion").click());
    assert.equal(sessionStorage.getItem("flowpilot.access_token"), null);
    assert.ok(document.getElementById("flow-email"));
  } finally {
    await act(async () => root.unmount());
    globalThis.fetch = originalFetch;
    setAccessToken(null);
  }
});
