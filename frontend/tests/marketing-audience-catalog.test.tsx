import test from "node:test";
import assert from "node:assert/strict";
import React, { act } from "react";
import { JSDOM } from "jsdom";
import { MarketingAudienceCatalog } from "../src/components/MarketingAudienceCatalog";
import { setAccessToken } from "../src/api/session";
import { crmProfile } from "./crm-fixture";
import type { AudienceOriginal } from "../src/marketing-audience-utils";
const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (actor = "manager", role = "responsable_institut") => `h.${Buffer.from(JSON.stringify({ sub: actor, role })).toString("base64url")}.s`;
const reply = (v: unknown) => new Response(JSON.stringify(v), { headers: { "Content-Type": "application/json" } });
const profile = crmProfile();
const original: AudienceOriginal = { id: "capture", institute_id: "i", actor_id: "manager", captured_at: profile.captured_at,
  request: { segments: [profile.segment!.state!], channel: "email", reason: "Selected capture", idempotency_key: "key" },
  summary: { page_count: 1, customer_count: 1, selected_count: 1, eligible_count: 0 }, complete_registered_cohort: true, delivery_authorized: false };
const retained = { capture_id: "capture", page_index: 0, observation: { institute_id: "i", captured_at: profile.captured_at,
  selection: { segments: original.request.segments, channel: "email", after: null }, next_after: null,
  items: [{ customer_id: "customer_a", profile, declaration: null, selected_segment: true, marketing_permission: "unknown",
    eligible_by_recorded_permission: false, delivery_authorized: false }], complete_institute_audience: false, delivery_authorized: false } };
async function click(text: string) {
  const button = [...document.querySelectorAll("button")].find(b => b.textContent!.includes(text)); assert.ok(button);
  await act(async () => button.click());
}
test("retained catalog independently verifies originals and hides corrupt page until clean retry", async () => {
  const savedFetch = globalThis.fetch, root = createRoot(document.getElementById("root")!); let corrupt = false; const paths: string[] = [];
  globalThis.fetch = async (url, options) => {
    assert.equal(new Headers(options?.headers).get("Authorization"), `Bearer ${token()}`); const path = String(url); paths.push(path);
    if (path.includes("?offset=")) return reply({ institute_id: "i", total: 1, offset: 0, limit: 20, items: [original] });
    if (path.includes("/pages/")) return reply(corrupt ? { ...retained, capture_id: "foreign" } : retained);
    return reply(original);
  };
  try {
    sessionStorage.clear(); setAccessToken(token()); await act(async () => root.render(<MarketingAudienceCatalog institute="i" />)); assert.equal(paths.length, 0);
    await click("Consulter les audiences retenues"); await click("Selected capture"); assert.equal(document.querySelectorAll("article").length, 1);
    assert.ok(paths.some(p => p.endsWith("/original/key"))); assert.ok(paths.some(p => p.endsWith("/capture")));
    assert.match(document.body.textContent!, /permission marketing : Inconnue/);
    corrupt = true; await click("Actualiser la page retenue"); assert.equal(document.querySelectorAll("article").length, 0); assert.match(document.body.textContent!, /Page retenue à vérifier/);
    corrupt = false; await click("Actualiser la page retenue"); assert.equal(document.querySelectorAll("article").length, 1);
  } finally { await act(async () => root.unmount()); globalThis.fetch = savedFetch; }
});
test("catalog denies reception and rejects foreign or mismatched totals", async () => {
  const savedFetch = globalThis.fetch, root = createRoot(document.getElementById("root")!); let calls = 0, total = 2;
  globalThis.fetch = async () => { calls++; return reply({ institute_id: "i", total, offset: 0, limit: 20, items: [original] }); };
  try {
    setAccessToken(token("manager", "accueil")); await act(async () => root.render(<MarketingAudienceCatalog institute="i" />)); assert.equal(calls, 0);
    setAccessToken(token()); await act(async () => root.render(<MarketingAudienceCatalog institute="i" />)); await click("Consulter les audiences retenues");
    assert.match(document.body.textContent!, /Catalogue des audiences à vérifier/); assert.doesNotMatch(document.body.textContent!, /Selected capture/);
    total = 1; await click("Consulter les audiences retenues"); assert.match(document.body.textContent!, /Selected capture/);
    await act(async () => root.render(<MarketingAudienceCatalog institute="foreign" />)); await click("Consulter les audiences retenues");
    assert.doesNotMatch(document.body.textContent!, /Selected capture/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = savedFetch; }
});
