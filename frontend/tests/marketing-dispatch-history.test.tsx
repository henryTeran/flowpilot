import test from "node:test";
import assert from "node:assert/strict";
import React, { act } from "react";
import { JSDOM } from "jsdom";
import { readFileSync } from "node:fs";
import { MarketingDispatchHistory } from "../src/components/MarketingDispatchHistory";
import { setAccessToken } from "../src/api/session";
const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const v = JSON.parse(readFileSync(new URL("./fixtures/marketing-dispatch-13ar.json", import.meta.url), "utf8"))[0];
const token = (actor = "manager", role = "responsable_institut") => `h.${Buffer.from(JSON.stringify({ sub: actor, role })).toString("base64url")}.s`;
const reply = (value: unknown) => new Response(JSON.stringify(value), { headers: { "Content-Type": "application/json" } });
async function click(label: string) {
  const button = [...document.querySelectorAll("button")].find(b => b.textContent === label)!;
  await act(async () => button.click());
  const deadline = Date.now() + 5000;
  while (button.isConnected && button.disabled && Date.now() < deadline) await act(async () => { await new Promise(r => setTimeout(r, 20)); });
  assert.equal(button.disabled, false);
}
test("retained intent and outcome reader independently verifies originals and hides corrupt reads", async () => {
  const root = createRoot(document.getElementById("root")!), saved = globalThis.fetch;
  let corrupt = false, corruptOutcome = false, empty = false, drifting = false, headReads = 0; const calls: string[] = [];
  globalThis.fetch = async (url, options) => {
    assert.equal(options?.method || "GET", "GET");
    const path = String(url); calls.push(path);
    if (path.includes("/outcomes")) {
      if (path.includes("?")) return reply(empty ? { ...v.outcome_page, total: 0, items: [] } : v.outcome_page);
      if (path.endsWith("/current")) { headReads++; return reply(empty ? null : drifting && headReads % 2 === 0 ? { ...v.outcome, actor_id: "advanced" } : v.outcome); }
      const o = v.outcome_page.items.find((o: any) => path.endsWith("/" + o.id) || path.endsWith("/" + o.request.idempotency_key));
      return reply(corruptOutcome ? { ...o, actor_id: "changed" } : o);
    }
    if (path.includes("/contact-declarations")) return reply(v.contact);
    if (path.includes("/campaigns/") && !path.includes("dispatch-intents")) return reply(v.approval);
    if (path.includes("?")) return reply(v.intent_page);
    return reply(corrupt ? { ...v.intent, request_fingerprint: "0".repeat(64) } : v.intent);
  };
  try {
    setAccessToken(token()); await act(async () => root.render(<MarketingDispatchHistory institute={v.institute_id} campaign={v.approval} />));
    assert.equal(calls.length, 0); await click("Vérifier les intentions conservées");
    assert.equal(document.querySelectorAll("article").length, 1);
    assert.doesNotMatch(document.body.textContent!, /secret-token/);
    await click("Vérifier les résultats conservés"); assert.match(document.body.textContent!, /Accepté par le fournisseur/);
    assert.match(document.body.textContent!, /ne signifie pas livraison/);
    assert.match(document.body.textContent!, /Résultat incertain/);
    drifting = true; headReads = 0; await click("Vérifier les résultats conservés");
    assert.doesNotMatch(document.body.textContent!, /Dernier résultat/); drifting = false;
    corruptOutcome = true; await click("Vérifier les résultats conservés");
    assert.doesNotMatch(document.body.textContent!, /Dernier résultat/); assert.match(document.body.textContent!, /Résultats conservés à vérifier/);
    corruptOutcome = false; empty = true; await click("Vérifier les résultats conservés"); assert.match(document.body.textContent!, /Aucun résultat conservé/);
    corrupt = true; await click("Vérifier les intentions conservées"); assert.equal(document.querySelectorAll("article").length, 0);
    corrupt = false; await click("Vérifier les intentions conservées"); assert.equal(document.querySelectorAll("article").length, 1);
    setAccessToken(token("reception", "accueil")); await act(async () => root.render(<MarketingDispatchHistory institute={v.institute_id} campaign={v.approval} />));
    assert.equal(document.querySelector("button"), null);
  } finally { await act(async () => root.unmount()); globalThis.fetch = saved; }
});
test("late retained catalog cannot populate a replaced actor", async () => {
  const root = createRoot(document.getElementById("root")!), saved = globalThis.fetch; let resolve!: (r: Response) => void;
  globalThis.fetch = async () => new Promise(r => { resolve = r; });
  try {
    setAccessToken(token()); await act(async () => root.render(<MarketingDispatchHistory institute={v.institute_id} campaign={v.approval} />));
    await act(async () => document.querySelector("button")!.click());
    setAccessToken(token("other")); await act(async () => root.render(<MarketingDispatchHistory institute={v.institute_id} campaign={v.approval} />));
    await act(async () => resolve(reply(v.intent_page))); assert.equal(document.querySelectorAll("article").length, 0);
  } finally { await act(async () => root.unmount()); globalThis.fetch = saved; }
});
