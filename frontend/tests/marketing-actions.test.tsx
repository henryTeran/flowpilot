import test from "node:test";
import assert from "node:assert/strict";
import React, { act } from "react";
import { JSDOM } from "jsdom";
import { MarketingCampaignActions } from "../src/components/MarketingCampaignActions";
import { setAccessToken } from "../src/api/session";
import { campaignDigest, type CampaignOriginal, type CampaignRequest } from "../src/marketing-campaign-utils";
const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (actor = "manager", role = "responsable_institut") => `h.${Buffer.from(JSON.stringify({ sub: actor, role })).toString("base64url")}.s`;
const storage = 'flowpilot.marketing-campaign-request:["i","manager","campaign"]';
const terms: CampaignRequest = { action: "review", campaign_id: "campaign", expected_revision_id: "draft", content: null, reason: "Explicit review", idempotency_key: "key" };
const reply = (v: unknown) => new Response(JSON.stringify(v), { headers: { "Content-Type": "application/json" } });
async function receipt(): Promise<CampaignOriginal> {
  const content = { institute_id: "i", channel: "email" as const, origin: "ai" as const, subject: "Subject", body: "Exact content", template_original_id: null,
    audience: { id: "audience", institute_id: "i", captured_at: "2026-10-07T00:00:00Z", customer_ids: ["customer"] } };
  return { request: terms, revision: { id: "review", campaign_id: "campaign", institute_id: "i", previous_id: "draft", state: "REVIEW", content,
    actor_id: "manager", reason: terms.reason, created_at: "2026-10-07T00:00:01Z", reviewed_digest: await campaignDigest(content), approved_digest: null,
    external_message_sent: false, delivery_authorized: false } };
}
async function resume() {
  const button = [...document.querySelectorAll("button")].find(b => b.textContent === "Reprendre la validation conservée"); assert.ok(button);
  await act(async () => { button.click(); });
  for (let attempt = 0; button.isConnected && button.disabled && attempt < 250; attempt++) {
    await act(async () => { await new Promise(r => setTimeout(r, 20)); });
  }
  assert.ok(!button.isConnected || !button.disabled, "Recovery action must settle within five seconds");
}
test("lost campaign POST resumes after remount through key/ID/current without another POST", async () => {
  const savedFetch = globalThis.fetch; let root = createRoot(document.getElementById("root")!);
  const o = await receipt(); let committed = false, posts = 0, changed = 0; const paths: string[] = [];
  globalThis.fetch = async (url, options) => {
    assert.equal(new Headers(options?.headers).get("Authorization"), `Bearer ${token()}`);
    const path = String(url); paths.push(path);
    if (options?.method === "POST") { posts++; committed = true; assert.deepEqual(JSON.parse(String(options.body)), terms); throw new TypeError("Lost response"); }
    return reply(committed ? o : null);
  };
  try {
    sessionStorage.clear(); setAccessToken(token()); sessionStorage.setItem(storage, JSON.stringify(terms));
    await act(async () => root.render(<MarketingCampaignActions institute="i" campaign="campaign" onChanged={() => changed++} />));
    await resume(); assert.equal(posts, 1); assert.ok(sessionStorage.getItem(storage)); assert.equal(changed, 0);
    await act(async () => root.unmount()); root = createRoot(document.getElementById("root")!);
    await act(async () => root.render(<MarketingCampaignActions institute="i" campaign="campaign" onChanged={() => changed++} />));
    await resume(); assert.equal(posts, 1); assert.equal(sessionStorage.getItem(storage), null); assert.equal(changed, 1);
    assert.ok(paths.some(p => p.endsWith("/review"))); assert.ok(paths.some(p => p.endsWith("/campaign/current")));
    assert.match(document.body.textContent!, /Original vérifié/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = savedFetch; sessionStorage.clear(); }
});
test("wrong actor or corrupted independent current preserves pending request", async () => {
  const savedFetch = globalThis.fetch, root = createRoot(document.getElementById("root")!); const o = await receipt(); let mode = "actor", posts = 0;
  globalThis.fetch = async (url, options) => {
    if (options?.method === "POST") posts++;
    return reply(mode === "actor" ? { ...o, revision: { ...o.revision, actor_id: "other" } }
      : String(url).endsWith("/current") ? { ...o, revision: { ...o.revision, reviewed_digest: "forged" } } : o);
  };
  try {
    sessionStorage.clear(); setAccessToken(token()); sessionStorage.setItem(storage, JSON.stringify(terms));
    await act(async () => root.render(<MarketingCampaignActions institute="i" campaign="campaign" onChanged={() => assert.fail("Must remain pending")} />));
    await resume(); assert.ok(sessionStorage.getItem(storage)); assert.match(document.body.textContent!, /Reçu de campagne à vérifier/);
    mode = "current"; await resume(); assert.ok(sessionStorage.getItem(storage)); assert.match(document.body.textContent!, /sélection courante à vérifier/); assert.equal(posts, 0);
  } finally { await act(async () => root.unmount()); globalThis.fetch = savedFetch; sessionStorage.clear(); }
});
test("invalid stored terms freeze writes and reception cannot recover manager request", async () => {
  const savedFetch = globalThis.fetch, root = createRoot(document.getElementById("root")!); let calls = 0;
  globalThis.fetch = async () => { calls++; return reply(null); };
  try {
    sessionStorage.clear(); setAccessToken(token()); sessionStorage.setItem(storage, JSON.stringify({ ...terms, action: "send" }));
    await act(async () => root.render(<MarketingCampaignActions institute="i" campaign="campaign" onChanged={() => {}} />));
    assert.match(document.body.textContent!, /Demande conservée invalide/); assert.ok([...document.querySelectorAll("button")].every(b => b.disabled));
    setAccessToken(token("manager", "accueil")); await act(async () => root.render(<MarketingCampaignActions institute="i" campaign="campaign" onChanged={() => {}} />));
    assert.equal(document.body.textContent, ""); assert.equal(calls, 0); assert.ok(sessionStorage.getItem(storage));
  } finally { await act(async () => root.unmount()); globalThis.fetch = savedFetch; sessionStorage.clear(); }
});
