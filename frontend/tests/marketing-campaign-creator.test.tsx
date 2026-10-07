import test from "node:test";
import assert from "node:assert/strict";
import React, { act } from "react";
import { JSDOM } from "jsdom";
import { MarketingCampaignCreator } from "../src/components/MarketingCampaignCreator";
import { setAccessToken } from "../src/api/session";
import type { CampaignRequest, CampaignOriginal } from "../src/marketing-campaign-utils";
const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (actor = "manager", role = "responsable_institut") => `h.${Buffer.from(JSON.stringify({ sub: actor, role })).toString("base64url")}.s`;
const storage = 'flowpilot.marketing-campaign-create-request:["i","manager"]';
const content = { channel: "email" as const, origin: "human" as const, subject: "Subject", body: "Literal", template_original_id: null, audience_id: "audience" };
const terms: CampaignRequest = { action: "create", campaign_id: null, expected_revision_id: null, content, reason: "Explicit draft", idempotency_key: "key" };
const original: CampaignOriginal = { request: terms, revision: { id: "revision", campaign_id: "root", institute_id: "i", previous_id: null, state: "DRAFT",
  content: { channel: content.channel, origin: content.origin, subject: content.subject, body: content.body, template_original_id: null, institute_id: "i",
    audience: { id: "audience", institute_id: "i", captured_at: "2026-10-07T00:00:00Z", customer_ids: ["customer"] } }, actor_id: "manager",
  reason: terms.reason, created_at: "2026-10-07T00:00:01Z", reviewed_digest: null, approved_digest: null, external_message_sent: false, delivery_authorized: false } };
const reply = (v: unknown) => new Response(JSON.stringify(v), { headers: { "Content-Type": "application/json" } });
async function click(text: string) {
  const button = [...document.querySelectorAll("button")].find(b => b.textContent === text); assert.ok(button);
  await act(async () => button.click());
  for (let attempt = 0; button.isConnected && button.disabled && attempt < 250; attempt++) await act(async () => { await new Promise(r => setTimeout(r, 20)); });
  assert.ok(!button.isConnected || !button.disabled);
}
test("draft recovery requires actor/terms and independent ID/current before clearing request", async () => {
  const savedFetch = globalThis.fetch, root = createRoot(document.getElementById("root")!); let mode = "actor", posts = 0, changed = 0;
  globalThis.fetch = async (url, options) => { if (options?.method === "POST") posts++;
    return reply(mode === "actor" ? { ...original, revision: { ...original.revision, actor_id: "other" } }
      : mode === "head" && String(url).endsWith("/current") ? { ...original, revision: { ...original.revision, campaign_id: "foreign" } } : original); };
  try {
    sessionStorage.clear(); setAccessToken(token()); sessionStorage.setItem(storage, JSON.stringify(terms));
    await act(async () => root.render(<MarketingCampaignCreator institute="i" onChanged={() => changed++} />));
    await click("Reprendre le brouillon conservé"); assert.ok(sessionStorage.getItem(storage)); assert.equal(changed, 0);
    mode = "head"; await click("Reprendre le brouillon conservé"); assert.ok(sessionStorage.getItem(storage)); assert.equal(changed, 0);
    mode = "good"; await click("Reprendre le brouillon conservé"); assert.equal(sessionStorage.getItem(storage), null); assert.equal(changed, 1); assert.equal(posts, 0);
    assert.match(document.body.textContent!, /Brouillon original vérifié/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = savedFetch; sessionStorage.clear(); }
});
test("source audience must agree with independent original before selecting recipients", async () => {
  const savedFetch = globalThis.fetch, root = createRoot(document.getElementById("root")!);
  const audience = { id: "audience", institute_id: "i", actor_id: "manager", captured_at: "2026-10-07T00:00:00Z", request: { segments: ["NEW"], channel: "email", reason: "Source", idempotency_key: "source" },
    summary: { page_count: 1, customer_count: 1, selected_count: 1, eligible_count: 1 }, complete_registered_cohort: true, delivery_authorized: false };
  globalThis.fetch = async url => reply(String(url).includes("?offset=") ? { institute_id: "i", total: 1, offset: 0, limit: 20, items: [audience] }
    : { ...audience, summary: { ...audience.summary, eligible_count: 0 } });
  try {
    sessionStorage.clear(); setAccessToken(token()); await act(async () => root.render(<MarketingCampaignCreator institute="i" />));
    await click("Préparer une campagne"); const select = document.querySelector("select")!;
    await act(async () => { select.value = "email"; select.dispatchEvent(new dom.window.Event("change", { bubbles: true })); });
    await click("Choisir une audience source"); await click("Source · email · 1 éligibles");
    assert.match(document.body.textContent!, /Audience source à vérifier/); assert.doesNotMatch(document.body.textContent!, /Audience sélectionnée/);
    assert.equal([...document.querySelectorAll("button")].find(b => b.textContent === "Enregistrer le brouillon")!.disabled, true);
  } finally { await act(async () => root.unmount()); globalThis.fetch = savedFetch; sessionStorage.clear(); }
});
test("invalid create storage and reception cannot initiate campaign writes", async () => {
  const savedFetch = globalThis.fetch, root = createRoot(document.getElementById("root")!); let calls = 0;
  globalThis.fetch = async () => { calls++; return reply(null); };
  try {
    sessionStorage.clear(); setAccessToken(token()); sessionStorage.setItem(storage, JSON.stringify({ ...terms, action: "send" }));
    await act(async () => root.render(<MarketingCampaignCreator institute="i" />)); assert.match(document.body.textContent!, /Demande conservée invalide/);
    assert.ok([...document.querySelectorAll("button")].every(b => b.disabled));
    setAccessToken(token("manager", "accueil")); await act(async () => root.render(<MarketingCampaignCreator institute="i" />)); assert.equal(document.body.textContent, ""); assert.equal(calls, 0);
  } finally { await act(async () => root.unmount()); globalThis.fetch = savedFetch; sessionStorage.clear(); }
});
