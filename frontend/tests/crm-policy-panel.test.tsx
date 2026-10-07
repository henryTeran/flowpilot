import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import React, { act } from "react";
import { CrmPolicyPanel, durationMicros } from "../src/components/CrmPolicyPanel";
import { setAccessToken } from "../src/api/session";
import { crmProfile } from "./crm-fixture";
const dom = new JSDOM("<!doctype html><div id='root'></div>", { url: "http://localhost:5173" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (actor = "manager", role = "responsable_institut") => `h.${Buffer.from(JSON.stringify({ role, sub: actor })).toString("base64url")}.s`;
const key = (actor = "manager") => `flowpilot.crm-policy-request:${JSON.stringify(["i", actor])}`;
const original = () => crmProfile().policy_original!;
const terms = () => { const { policy, previous_policy_id, reason, idempotency_key } = original(); return { policy, previous_policy_id, reason, idempotency_key }; };
const reply = (v: unknown) => new Response(JSON.stringify(v), { headers: { "Content-Type": "application/json" } });
const button = (text: string) => [...document.querySelectorAll<HTMLButtonElement>("button")].find(b => b.textContent === text)!;
function save(actor = "manager") { sessionStorage.clear(); setAccessToken(token(actor)); sessionStorage.setItem(key(actor), JSON.stringify(terms())); }

test("committed policy recovery retains request through a failed current read and never reposts", async () => {
  const fetch = globalThis.fetch, root = createRoot(document.getElementById("root")!); let currents = 0, posts = 0, changed = 0;
  save(); globalThis.fetch = async (url, init) => {
    if (init?.method === "POST") posts++;
    if (String(url).endsWith("/current") && ++currents === 2) return reply({ institute_id: "foreign" });
    return reply(original());
  };
  try {
    await act(async () => root.render(<CrmPolicyPanel institute="i" onChanged={() => changed++} />));
    await act(async () => button("Reprendre la demande CRM conservée").click());
    assert.equal(posts, 0); assert.equal(changed, 0); assert.ok(sessionStorage.getItem(key())); assert.match(document.body.textContent!, /Relisez/);
    await act(async () => button("Actualiser la politique").click());
    await act(async () => button("Reprendre la demande CRM conservée").click());
    assert.equal(posts, 0); assert.equal(changed, 1); assert.equal(sessionStorage.getItem(key()), null); assert.match(document.body.textContent!, /originale vérifiée/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = fetch; }
});
test("lost policy POST reply survives remount and exact original reread guards completion", async () => {
  const fetch = globalThis.fetch; let root = createRoot(document.getElementById("root")!); let committed = false, posts = 0, forge = true, reads = 0;
  save(); globalThis.fetch = async (url, init) => {
    if (init?.method === "POST") { committed = true; posts++; throw new Error("Lost reply"); }
    if (String(url).includes("/original/")) {
      if (!committed) return reply(null);
      const r = original(); if (++reads === 2 && forge) r.created_at = "2026-10-06T00:00:00.000001Z";
      return reply(r);
    }
    return reply(original());
  };
  try {
    await act(async () => root.render(<CrmPolicyPanel institute="i" />)); await act(async () => button("Reprendre la demande CRM conservée").click());
    assert.equal(posts, 1); assert.ok(sessionStorage.getItem(key()));
    await act(async () => root.unmount()); root = createRoot(document.getElementById("root")!);
    await act(async () => root.render(<CrmPolicyPanel institute="i" />)); await act(async () => button("Reprendre la demande CRM conservée").click());
    assert.ok(sessionStorage.getItem(key())); assert.match(document.body.textContent!, /Original relu/);
    forge = false; await act(async () => button("Reprendre la demande CRM conservée").click());
    assert.equal(posts, 1); assert.equal(sessionStorage.getItem(key()), null);
  } finally { await act(async () => root.unmount()); globalThis.fetch = fetch; }
});
test("prior actor and invalid saved policy cannot issue writes or clear original storage", async () => {
  const fetch = globalThis.fetch, root = createRoot(document.getElementById("root")!); let posts = 0, resolve: (v: Response) => void = () => {};
  save(); globalThis.fetch = async (url, init) => {
    if (init?.method === "POST") posts++;
    return String(url).includes("/original/") ? new Promise(r => { resolve = r; }) : reply(original());
  };
  try {
    await act(async () => root.render(<CrmPolicyPanel institute="i" />)); await act(async () => button("Reprendre la demande CRM conservée").click());
    setAccessToken(token("other")); await act(async () => root.render(<CrmPolicyPanel institute="i" />));
    await act(async () => resolve(reply(null))); assert.equal(posts, 0); assert.ok(sessionStorage.getItem(key()));
    sessionStorage.setItem(key("other"), "{}"); setAccessToken(token("other", "accueil")); await act(async () => root.render(<CrmPolicyPanel institute="i" />));
    setAccessToken(token("other")); await act(async () => root.render(<CrmPolicyPanel institute="i" />));
    assert.match(document.body.textContent!, /invalide/); assert.equal(posts, 0); assert.equal(sessionStorage.getItem(key("other")), "{}");
  } finally { await act(async () => root.unmount()); globalThis.fetch = fetch; }
});
test("duration input retains exact microseconds and rejects coercion, negatives and overflow", () => {
  assert.equal(durationMicros("0.000001", "secondes"), 1);
  assert.equal(durationMicros("1,5", "jours"), 129600000000);
  assert.equal(durationMicros("2", "heures"), 7200000000);
  for (const value of ["-1", "1e3", "NaN", "0", "0.0000001", "999999999999"]) assert.equal(durationMicros(value, "jours"), undefined);
});
