import test from "node:test";
import assert from "node:assert/strict";
import React, { act } from "react";
import { JSDOM } from "jsdom";
import { MarketingContactEditor } from "../src/components/MarketingContactEditor";
import { setAccessToken } from "../src/api/session";
import type { ContactRequest, ContactOriginal } from "../src/marketing-contact-utils";
const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (actor = "manager", role = "responsable_institut") => `h.${Buffer.from(JSON.stringify({ sub: actor, role })).toString("base64url")}.s`;
const storage = 'flowpilot.marketing-contact-request:["i","c","manager"]';
const terms: ContactRequest = { declaration: { institute_id: "i", customer_id: "c", purpose: "marketing", communications: ["email", "sms", "push"].map(channel => ({
  channel: channel as "email" | "sms" | "push", permission: "unknown", permission_evidence: null, destination: null })) },
  previous_id: null, reason: "Explicit contact declaration", idempotency_key: "original-key" };
const original: ContactOriginal = { ...terms, id: "original", actor_id: "manager", created_at: "2026-10-07T00:00:00Z" };
const reply = (v: unknown) => new Response(JSON.stringify(v), { headers: { "Content-Type": "application/json" } });
const click = async (name: string) => act(async () => [...document.querySelectorAll("button")].find(b => b.textContent === name)!.click());

test("contact lost reply remount resumes original once and corrupt independent head retains intent", async () => {
  const fetch = globalThis.fetch; let root = createRoot(document.getElementById("root")!), committed = false, posts = 0, corrupt = false;
  globalThis.fetch = async (url, options) => {
    if (options?.method === "POST") { posts++; committed = true; throw new Error("Committed reply lost"); }
    if (!committed) return reply(null);
    return reply(corrupt && String(url).endsWith("/current") ? { ...original, declaration: { ...terms.declaration, customer_id: "foreign" } } : original);
  };
  try {
    sessionStorage.clear(); setAccessToken(token()); sessionStorage.setItem(storage, JSON.stringify(terms));
    await act(async () => root.render(<MarketingContactEditor institute="i" customer="c" />));
    await click("Reprendre les contacts conservés"); assert.equal(posts, 1); assert.ok(sessionStorage.getItem(storage));
    await act(async () => root.unmount()); root = createRoot(document.getElementById("root")!);
    await act(async () => root.render(<MarketingContactEditor institute="i" customer="c" />));
    corrupt = true; await click("Reprendre les contacts conservés"); assert.equal(posts, 1); assert.ok(sessionStorage.getItem(storage));
    assert.match(document.body.textContent!, /Original ou contacts courants à vérifier/);
    corrupt = false; await click("Reprendre les contacts conservés"); assert.equal(posts, 1); assert.equal(sessionStorage.getItem(storage), null);
    assert.match(document.body.textContent!, /Contacts originaux vérifiés/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = fetch; sessionStorage.clear(); }
});

test("contact actor/full terms and independent preparation source cannot silently change", async () => {
  const fetch = globalThis.fetch, root = createRoot(document.getElementById("root")!); let mode = "actor", posts = 0;
  globalThis.fetch = async (url, options) => {
    if (options?.method === "POST") posts++;
    return reply(mode === "actor" ? { ...original, actor_id: "other" } : mode === "terms" ? { ...original, reason: "Other reason" }
      : mode === "id" && String(url).endsWith("/original") ? { ...original, reason: "Other original" } : original);
  };
  try {
    sessionStorage.clear(); setAccessToken(token()); sessionStorage.setItem(storage, JSON.stringify(terms));
    await act(async () => root.render(<MarketingContactEditor institute="i" customer="c" />));
    for (const value of ["actor", "terms", "id"]) { mode = value; await click("Reprendre les contacts conservés"); assert.ok(sessionStorage.getItem(storage)); }
    mode = "good"; await click("Reprendre les contacts conservés"); assert.equal(sessionStorage.getItem(storage), null); assert.equal(posts, 0);
    mode = "id"; await click("Préparer les contacts marketing"); assert.equal(document.querySelector("form"), null);
    assert.match(document.body.textContent!, /Original de contacts à vérifier/);
    mode = "good"; await click("Préparer les contacts marketing"); assert.ok(document.querySelector("form")); assert.equal(posts, 0);
  } finally { await act(async () => root.unmount()); globalThis.fetch = fetch; sessionStorage.clear(); }
});

test("invalid contact storage freezes writes and reception cannot access editor", async () => {
  const root = createRoot(document.getElementById("root")!), fetch = globalThis.fetch;
  let resolve: (r: Response) => void = () => {};
  try {
    sessionStorage.clear(); setAccessToken(token()); sessionStorage.setItem(storage, JSON.stringify({ ...terms, declaration: { ...terms.declaration, customer_id: "foreign" } }));
    await act(async () => root.render(<MarketingContactEditor institute="i" customer="c" />));
    assert.match(document.body.textContent!, /Demande conservée invalide/);
    assert.equal([...document.querySelectorAll("button")].find(b => b.textContent === "Préparer les contacts marketing")!.disabled, true);
    sessionStorage.setItem(storage, JSON.stringify(terms));
    setAccessToken(token("other")); await act(async () => root.render(<MarketingContactEditor institute="i" customer="c" />));
    setAccessToken(token()); await act(async () => root.render(<MarketingContactEditor institute="i" customer="c" />));
    globalThis.fetch = async () => new Promise(r => { resolve = r; });
    await click("Reprendre les contacts conservés");
    setAccessToken(token("other")); await act(async () => root.render(<MarketingContactEditor institute="i" customer="c" />));
    await act(async () => resolve(reply(original))); assert.ok(sessionStorage.getItem(storage));
    assert.doesNotMatch(document.body.textContent!, /Contacts originaux vérifiés/);
    setAccessToken(token("manager", "accueil")); await act(async () => root.render(<MarketingContactEditor institute="i" customer="c" />));
    assert.equal(document.body.textContent, "");
  } finally { await act(async () => root.unmount()); globalThis.fetch = fetch; sessionStorage.clear(); }
});
