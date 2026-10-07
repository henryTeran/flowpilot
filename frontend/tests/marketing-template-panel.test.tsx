import test from "node:test";
import assert from "node:assert/strict";
import React, { act } from "react";
import { JSDOM } from "jsdom";
import { MarketingTemplatePanel } from "../src/components/MarketingTemplatePanel";
import { setAccessToken } from "../src/api/session";
import type { TemplateRequest, TemplateOriginal } from "../src/marketing-template-utils";
const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (actor = "manager", role = "responsable_institut") => `h.${Buffer.from(JSON.stringify({ sub: actor, role })).toString("base64url")}.s`;
const storage = 'flowpilot.marketing-template-request:["i","manager"]';
const terms: TemplateRequest = { template_id: null, previous_id: null, content: { name: "Template", channel: "email", origin: "ai", subject: "Subject", body: "Literal {customer_name}" }, reason: "Explicit template", idempotency_key: "key" };
const original: TemplateOriginal = { id: "revision", template_id: "root", institute_id: "i", previous_id: null, actor_id: "manager", created_at: "2026-10-07T00:00:00Z", request: terms, content: terms.content };
const reply = (v: unknown) => new Response(JSON.stringify(v), { headers: { "Content-Type": "application/json" } });
const resume = async () => act(async () => [...document.querySelectorAll("button")].find(b => b.textContent === "Reprendre le template conservé")!.click());
test("template recovery requires exact actor plus independently coherent ID/current reads", async () => {
  const savedFetch = globalThis.fetch, root = createRoot(document.getElementById("root")!); let mode = "actor", posts = 0;
  globalThis.fetch = async (url, options) => {
    if (options?.method === "POST") posts++;
    return reply(mode === "actor" ? { ...original, actor_id: "other" } : mode === "head" && String(url).endsWith("/current") ? { ...original, template_id: "foreign" } : original);
  };
  try {
    sessionStorage.clear(); setAccessToken(token()); sessionStorage.setItem(storage, JSON.stringify(terms));
    await act(async () => root.render(<MarketingTemplatePanel institute="i" />)); await resume(); assert.ok(sessionStorage.getItem(storage)); assert.match(document.body.textContent!, /Reçu de template à vérifier/);
    mode = "head"; await resume(); assert.ok(sessionStorage.getItem(storage)); assert.match(document.body.textContent!, /sélection de template à vérifier/);
    mode = "good"; await resume(); assert.equal(sessionStorage.getItem(storage), null); assert.match(document.body.textContent!, /Original de template vérifié/); assert.equal(posts, 0);
  } finally { await act(async () => root.unmount()); globalThis.fetch = savedFetch; sessionStorage.clear(); }
});
test("template correction prepare refuses foreign current and invalid storage freezes writes", async () => {
  const savedFetch = globalThis.fetch, root = createRoot(document.getElementById("root")!); let calls = 0;
  globalThis.fetch = async url => { calls++; return reply(String(url).includes("?offset=")
    ? { institute_id: "i", total: 1, offset: 0, limit: 20, items: [original] } : { ...original, institute_id: "foreign" }); };
  try {
    sessionStorage.clear(); setAccessToken(token()); await act(async () => root.render(<MarketingTemplatePanel institute="i" />));
    await act(async () => [...document.querySelectorAll("button")].find(b => b.textContent === "Consulter les templates")!.click());
    await act(async () => [...document.querySelectorAll("button")].find(b => b.textContent!.includes("préparer une correction"))!.click());
    assert.match(document.body.textContent!, /Template courant à vérifier/); assert.equal(document.querySelector("form"), null);
    setAccessToken(token("other")); await act(async () => root.render(<MarketingTemplatePanel institute="i" />));
    setAccessToken(token()); sessionStorage.setItem(storage, JSON.stringify({ ...terms, previous_id: "missing-root" }));
    await act(async () => root.render(<MarketingTemplatePanel institute="i" />)); assert.match(document.body.textContent!, /Demande conservée invalide/);
    assert.ok([...document.querySelectorAll("button")].every(b => b.disabled)); const before = calls;
    setAccessToken(token("manager", "accueil")); await act(async () => root.render(<MarketingTemplatePanel institute="i" />)); assert.equal(document.body.textContent, ""); assert.equal(calls, before);
  } finally { await act(async () => root.unmount()); globalThis.fetch = savedFetch; sessionStorage.clear(); }
});
