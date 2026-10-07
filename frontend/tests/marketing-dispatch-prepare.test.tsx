import test from "node:test";
import assert from "node:assert/strict";
import React, { act } from "react";
import { JSDOM } from "jsdom";
import { readFileSync } from "node:fs";
import { MarketingDispatchPrepare } from "../src/components/MarketingDispatchPrepare";
import { dispatchFingerprint } from "../src/marketing-dispatch-utils";
import { setAccessToken } from "../src/api/session";
const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const vector = JSON.parse(readFileSync(new URL("./fixtures/marketing-dispatch-13ar.json", import.meta.url), "utf8"))[0];
const props = { institute: vector.institute_id, campaign: vector.approval, customer: vector.intent.request.customer_id, contact: vector.contact, eligible: true };
const token = (actor = "manager", role = "responsable_institut") => `h.${Buffer.from(JSON.stringify({ sub: actor, role })).toString("base64url")}.s`;
const storage = `flowpilot.marketing-dispatch-request:${JSON.stringify([props.institute, "manager", props.campaign.revision.campaign_id, props.customer])}`;
const reply = (value: unknown) => new Response(JSON.stringify(value), { headers: { "Content-Type": "application/json" } });
async function click(text: string) {
  const button = [...document.querySelectorAll("button")].find(b => b.textContent === text); assert.ok(button);
  await act(async () => button.click());
  const deadline = Date.now() + 5000;
  while (button.isConnected && button.disabled && Date.now() < deadline) await act(async () => { await new Promise(r => setTimeout(r, 20)); });
}
async function fill(value: string) {
  const input = document.querySelector("input")!;
  await act(async () => { Object.getOwnPropertyDescriptor(dom.window.HTMLInputElement.prototype, "value")!.set!.call(input, value);
    input.dispatchEvent(new dom.window.Event("input", { bubbles: true })); });
}

test("native preparation loses POST response then recovers historical sources after withdrawal with no second POST", async () => {
  const savedFetch = globalThis.fetch; let root = createRoot(document.getElementById("root")!);
  let retained: any = null, posts = 0; const paths: string[] = [];
  globalThis.fetch = async (url, options) => {
    const path = String(url); paths.push(path);
    assert.equal(new Headers(options?.headers).get("Authorization"), `Bearer ${token()}`);
    if (options?.method === "POST") {
      posts++; const request = JSON.parse(String(options.body));
      assert.deepEqual({ ...request, reason: vector.intent.request.reason, idempotency_key: vector.intent.request.idempotency_key }, vector.intent.request);
      assert.equal(request.reason, "Explicit native preparation");
      retained = structuredClone(vector.intent); retained.request = request; retained.submission.idempotency_key = request.idempotency_key;
      retained.request_fingerprint = await dispatchFingerprint(retained.submission); throw new TypeError("Lost committed reply");
    }
    if (path.includes("dispatch-accounts?")) return reply(vector.account_page);
    if (path.includes("dispatch-accounts/")) return reply(vector.intent.submission.account);
    if (path.includes("dispatch-intents")) return reply(retained);
    if (path.includes("contact-declarations")) return reply(vector.contact);
    return reply(vector.approval);
  };
  try {
    sessionStorage.clear(); setAccessToken(token());
    await act(async () => root.render(<MarketingDispatchPrepare {...props} />));
    assert.equal(paths.length, 0); await click("Choisir un compte autorisé");
    const select = document.querySelector("select")!;
    await act(async () => { select.value = vector.intent.submission.account.account_id; select.dispatchEvent(new dom.window.Event("change", { bubbles: true })); });
    await fill("Explicit native preparation"); await click("Conserver l’intention");
    assert.equal(posts, 1); assert.ok(sessionStorage.getItem(storage)); assert.match(document.body.textContent!, /Préparation conservée/);
    const stored = JSON.parse(sessionStorage.getItem(storage)!); assert.deepEqual(Object.keys(stored).sort(), ["account", "request"]);
    assert.equal(JSON.stringify(stored).includes("explicit-device-token"), false);
    await act(async () => root.unmount()); root = createRoot(document.getElementById("root")!);
    const withdrawn = structuredClone(props.contact); withdrawn.declaration.communications[0].permission = "refused";
    await act(async () => root.render(<MarketingDispatchPrepare {...props} contact={withdrawn} eligible={false} />));
    const reads = paths.length; await click("Reprendre la préparation conservée");
    assert.equal(posts, 1); assert.equal(sessionStorage.getItem(storage), null); assert.match(document.body.textContent!, /Intention originale vérifiée/);
    assert.equal(paths.slice(reads).some(path => path.includes("dispatch-accounts")), false);
    assert.equal(paths.slice(reads).some(path => path.includes("contact-declarations") && path.endsWith("/current")), false);
  } finally { await act(async () => root.unmount()); globalThis.fetch = savedFetch; sessionStorage.clear(); }
});

test("corrupted actor or independent intent/account source keeps protected terms without another POST", async () => {
  const savedFetch = globalThis.fetch, root = createRoot(document.getElementById("root")!); let mode = "actor", posts = 0;
  globalThis.fetch = async (url, options) => {
    if (options?.method === "POST") posts++;
    const path = String(url);
    if (path.includes("dispatch-intents")) {
      if (mode === "actor") return reply({ ...vector.intent, submission: { ...vector.intent.submission, actor_id: "foreign" } });
      if (mode === "id" && path.endsWith(vector.intent.id)) return reply({ ...vector.intent, request_fingerprint: "0".repeat(64) });
      return reply(vector.intent);
    }
    if (path.includes("contact-declarations")) return reply(vector.contact);
    return reply(vector.approval);
  };
  try {
    sessionStorage.clear(); setAccessToken(token()); sessionStorage.setItem(storage, JSON.stringify({ request: vector.intent.request, account: vector.intent.submission.account }));
    await act(async () => root.render(<MarketingDispatchPrepare {...props} />));
    await click("Reprendre la préparation conservée"); assert.ok(sessionStorage.getItem(storage)); assert.equal(posts, 0);
    mode = "id"; await click("Reprendre la préparation conservée"); assert.ok(sessionStorage.getItem(storage)); assert.equal(posts, 0);
    mode = "good"; await click("Reprendre la préparation conservée"); assert.equal(sessionStorage.getItem(storage), null); assert.equal(posts, 0);
  } finally { await act(async () => root.unmount()); globalThis.fetch = savedFetch; sessionStorage.clear(); }
});

test("invalid stored request freezes writes and reception cannot read or recover it", async () => {
  const savedFetch = globalThis.fetch, root = createRoot(document.getElementById("root")!); let calls = 0;
  globalThis.fetch = async () => { calls++; return reply(null); };
  try {
    sessionStorage.clear(); setAccessToken(token()); sessionStorage.setItem(storage, JSON.stringify({ request: { ...vector.intent.request, customer_id: "foreign" }, account: vector.intent.submission.account }));
    await act(async () => root.render(<MarketingDispatchPrepare {...props} />));
    assert.match(document.body.textContent!, /Demande conservée invalide/); assert.ok([...document.querySelectorAll("button")].every(button => button.disabled));
    setAccessToken(token("manager", "accueil")); await act(async () => root.render(<MarketingDispatchPrepare {...props} />));
    assert.equal(document.body.textContent, ""); assert.equal(calls, 0); assert.ok(sessionStorage.getItem(storage));
  } finally { await act(async () => root.unmount()); globalThis.fetch = savedFetch; sessionStorage.clear(); }
});

test("changed fresh account before a first POST leaves no stuck new request or mutation", async () => {
  const savedFetch = globalThis.fetch, root = createRoot(document.getElementById("root")!); let posts = 0;
  globalThis.fetch = async (url, options) => {
    const path = String(url); if (options?.method === "POST") posts++;
    if (path.includes("dispatch-intents")) return reply(null);
    if (path.includes("dispatch-accounts?")) return reply(vector.account_page);
    if (path.includes("dispatch-accounts/")) return reply({ ...vector.intent.submission.account, mode: "live" });
    if (path.includes("contact-declarations")) return reply(vector.contact);
    return reply(vector.approval);
  };
  try {
    sessionStorage.clear(); setAccessToken(token()); await act(async () => root.render(<MarketingDispatchPrepare {...props} />));
    await click("Choisir un compte autorisé");
    const select = document.querySelector("select")!; await act(async () => { select.value = vector.intent.submission.account.account_id; select.dispatchEvent(new dom.window.Event("change", { bubbles: true })); });
    await fill("Explicit native preparation"); await click("Conserver l’intention");
    assert.equal(posts, 0); assert.equal(sessionStorage.getItem(storage), null);
    assert.match(document.body.textContent!, /compte courant à relire/); assert.equal(document.querySelector("input")!.disabled, false);
  } finally { await act(async () => root.unmount()); globalThis.fetch = savedFetch; sessionStorage.clear(); }
});

test("Push account for another application cannot prepare or expose its device token", async () => {
  const savedFetch = globalThis.fetch, root = createRoot(document.getElementById("root")!);
  const push = JSON.parse(readFileSync(new URL("./fixtures/marketing-dispatch-13ar.json", import.meta.url), "utf8"))[2]; let calls = 0;
  globalThis.fetch = async () => { calls++; return reply({ ...push.account_page, items: [{ ...push.intent.submission.account, push_application: "other-app" }] }); };
  try {
    sessionStorage.clear(); setAccessToken(token());
    await act(async () => root.render(<MarketingDispatchPrepare institute={push.institute_id} campaign={push.approval} customer={push.intent.request.customer_id} contact={push.contact} eligible />));
    await click("Choisir un compte autorisé");
    const select = document.querySelector("select")!; await act(async () => { select.value = push.intent.submission.account.account_id; select.dispatchEvent(new dom.window.Event("change", { bubbles: true })); });
    assert.match(document.body.textContent!, /Ce compte ne correspond pas/);
    const prepare = [...document.querySelectorAll("button")].find(button => button.textContent === "Conserver l’intention"); assert.ok(prepare?.disabled);
    assert.equal(calls, 1); assert.equal(sessionStorage.length, 1); // Access token only.
    assert.equal(document.body.textContent!.includes("explicit-device-token"), false);
  } finally { await act(async () => root.unmount()); globalThis.fetch = savedFetch; sessionStorage.clear(); }
});
