import test from "node:test";
import assert from "node:assert/strict";
import React, { act } from "react";
import { JSDOM } from "jsdom";
import { MarketingAudiencePanel } from "../src/components/MarketingAudiencePanel";
import { setAccessToken } from "../src/api/session";
import type { AudienceRequest, AudienceOriginal } from "../src/marketing-audience-utils";
const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (actor = "manager", role = "responsable_institut") => `h.${Buffer.from(JSON.stringify({ sub: actor, role })).toString("base64url")}.s`;
const storage = 'flowpilot.marketing-audience-request:["i","manager"]';
const terms: AudienceRequest = { segments: ["NEW"], channel: "email", reason: "Explicit capture", idempotency_key: "key" };
const original: AudienceOriginal = { id: "capture", institute_id: "i", actor_id: "manager", captured_at: "2026-10-07T00:00:00Z", request: terms,
  summary: { page_count: 2, customer_count: 55, selected_count: 55, eligible_count: 2 }, complete_registered_cohort: true, delivery_authorized: false };
const reply = (v: unknown) => new Response(JSON.stringify(v), { headers: { "Content-Type": "application/json" } });
const resume = async () => act(async () => [...document.querySelectorAll("button")].find(b => b.textContent === "Reprendre la capture conservée")!.click());
test("capture recovery retains mismatched actor/independent original and closes only after exact reads", async () => {
  const savedFetch = globalThis.fetch, root = createRoot(document.getElementById("root")!); let mode = "actor", posts = 0; const paths: string[] = [];
  globalThis.fetch = async (url, options) => {
    paths.push(String(url)); if (options?.method === "POST") posts++;
    return reply(mode === "actor" ? { ...original, actor_id: "other" } : mode === "id" && String(url).endsWith("/capture")
      ? { ...original, summary: { ...original.summary, eligible_count: 1 } } : original);
  };
  try {
    sessionStorage.clear(); setAccessToken(token()); sessionStorage.setItem(storage, JSON.stringify(terms));
    await act(async () => root.render(<MarketingAudiencePanel institute="i" />));
    await resume(); assert.ok(sessionStorage.getItem(storage)); assert.match(document.body.textContent!, /Capture originale à vérifier/);
    mode = "id"; await resume(); assert.ok(sessionStorage.getItem(storage)); assert.match(document.body.textContent!, /Original relu à vérifier/);
    mode = "good"; await resume(); assert.equal(sessionStorage.getItem(storage), null); assert.equal(posts, 0);
    assert.match(document.body.textContent!, /55 clientes observées/); assert.ok(paths.some(p => p.endsWith("/capture")));
  } finally { await act(async () => root.unmount()); globalThis.fetch = savedFetch; sessionStorage.clear(); }
});
test("invalid capture intent freezes form and old actor response cannot close storage", async () => {
  const savedFetch = globalThis.fetch, root = createRoot(document.getElementById("root")!); let resolve: (r: Response) => void = () => {};
  globalThis.fetch = async () => new Promise(r => { resolve = r; });
  try {
    sessionStorage.clear(); setAccessToken(token()); sessionStorage.setItem(storage, JSON.stringify({ ...terms, segments: [] }));
    await act(async () => root.render(<MarketingAudiencePanel institute="i" />));
    assert.match(document.body.textContent!, /Demande conservée invalide/); assert.equal(document.querySelector("fieldset")!.disabled, true);
    setAccessToken(token("other")); await act(async () => root.render(<MarketingAudiencePanel institute="i" />));
    setAccessToken(token()); sessionStorage.setItem(storage, JSON.stringify(terms)); await act(async () => root.render(<MarketingAudiencePanel institute="i" />));
    await resume(); setAccessToken(token("other")); await act(async () => root.render(<MarketingAudiencePanel institute="i" />));
    await act(async () => resolve(reply(original))); assert.ok(sessionStorage.getItem(storage)); assert.doesNotMatch(document.body.textContent!, /Capture originale vérifiée/);
    setAccessToken(token("manager", "accueil")); await act(async () => root.render(<MarketingAudiencePanel institute="i" />)); assert.equal(document.body.textContent, "");
  } finally { await act(async () => root.unmount()); globalThis.fetch = savedFetch; sessionStorage.clear(); }
});
