import test from "node:test";
import assert from "node:assert/strict";
import React, { act } from "react";
import { JSDOM } from "jsdom";
import { MarketingPanel } from "../src/components/MarketingPanel";
import { setAccessToken } from "../src/api/session";
import type { CampaignOriginal } from "../src/marketing-campaign-utils";
const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (actor = "manager", role = "responsable_institut") => `h.${Buffer.from(JSON.stringify({ sub: actor, role })).toString("base64url")}.s`;
const reply = (v: unknown) => new Response(JSON.stringify(v), { headers: { "Content-Type": "application/json" } });
function original(): CampaignOriginal {
  return { request: { action: "create", campaign_id: null, expected_revision_id: null, content: { channel: "email", origin: "human", subject: "Relance test",
    body: "Texte <script>literal</script>", audience_id: "audience", template_original_id: null }, reason: "Explicit draft", idempotency_key: "key" },
    revision: { id: "revision", campaign_id: "campaign", institute_id: "i", previous_id: null, state: "DRAFT", content: { institute_id: "i",
      channel: "email", origin: "human", subject: "Relance test", body: "Texte <script>literal</script>", template_original_id: null,
      audience: { id: "audience", institute_id: "i", captured_at: "2026-10-07T00:00:00Z", customer_ids: ["customer"] } }, actor_id: "manager",
      reason: "Explicit draft", created_at: "2026-10-07T00:00:01Z", reviewed_digest: null, approved_digest: null, external_message_sent: false, delivery_authorized: false } };
}
async function click(label: string) {
  const button = [...document.querySelectorAll("button")].find(b => b.textContent?.includes(label)); assert.ok(button, label);
  await act(async () => { button.click(); await new Promise(r => setTimeout(r, 20)); });
}
test("native campaign catalog/history uses signed reads and hides malformed fresh facts", async () => {
  const saved = globalThis.fetch, root = createRoot(document.getElementById("root")!); let corrupt = false;
  const a = original(), calls: string[] = [];
  globalThis.fetch = async (url, options) => {
    assert.equal(new Headers(options?.headers).get("Authorization"), `Bearer ${token()}`);
    const path = String(url); calls.push(path);
    if (path.includes("/audit?")) return reply({ institute_id: "i", campaign_id: "campaign", total: corrupt ? 2 : 1, offset: 0, limit: 20, originals: [a] });
    if (path.includes("/campaigns?")) return reply({ institute_id: "i", total: 1, offset: 0, limit: 20, items: [a] });
    return reply(a);
  };
  try {
    setAccessToken(token()); await act(async () => root.render(<MarketingPanel institute="i" />));
    await click("Relance test"); assert.match(document.body.textContent!, /1 destinataires retenus/);
    assert.equal(document.querySelector("script"), null); assert.match(document.body.textContent!, /<script>literal/);
    assert.equal(document.querySelectorAll("article").length, 1);
    assert.ok(calls.some(p => p.endsWith("/revision"))); assert.ok(calls.some(p => p.endsWith("/campaign/current")));
    corrupt = true; await click("Actualiser l’historique"); assert.match(document.body.textContent!, /Historique à vérifier/);
    assert.equal(document.querySelectorAll("article").length, 0); assert.doesNotMatch(document.body.textContent!, /destinataires retenus/);
    corrupt = false; await click("Actualiser l’historique"); assert.equal(document.querySelectorAll("article").length, 1);
  } finally { await act(async () => root.unmount()); globalThis.fetch = saved; }
});
test("native marketing denies reception and isolates late old actor/institute catalogs", async () => {
  const saved = globalThis.fetch, root = createRoot(document.getElementById("root")!);
  const pending: ((r: Response) => void)[] = [];
  globalThis.fetch = async () => new Promise(resolve => pending.push(resolve));
  try {
    setAccessToken(token("manager", "accueil")); await act(async () => root.render(<MarketingPanel institute="i" />)); assert.equal(pending.length, 0);
    setAccessToken(token()); await act(async () => root.render(<MarketingPanel institute="i" />));
    setAccessToken(token("new")); await act(async () => root.render(<MarketingPanel institute="other" />));
    await act(async () => pending[0](reply({ institute_id: "i", total: 1, offset: 0, limit: 20, items: [original()] })));
    assert.doesNotMatch(document.body.textContent!, /Relance test/);
    await act(async () => pending[1](reply({ institute_id: "other", total: 0, offset: 0, limit: 20, items: [] })));
    assert.match(document.body.textContent!, /Aucune campagne enregistrée/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = saved; }
});
