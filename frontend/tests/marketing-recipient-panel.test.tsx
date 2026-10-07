import test from "node:test";
import assert from "node:assert/strict";
import React, { act } from "react";
import { JSDOM } from "jsdom";
import { MarketingRecipientPanel } from "../src/components/MarketingRecipientPanel";
import { setAccessToken } from "../src/api/session";
import { recipientFixture } from "./marketing-recipient-fixture";
const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (actor = "manager", role = "responsable_institut") => `h.${Buffer.from(JSON.stringify({ sub: actor, role })).toString("base64url")}.s`;
const reply = (v: unknown) => new Response(JSON.stringify(v), { headers: { "Content-Type": "application/json" } });
async function click(settle = true) {
  await act(async () => { document.querySelector("button")!.click(); });
  if (settle) {
    const deadline = Date.now() + 5000;
    while (document.querySelector("button")!.disabled && Date.now() < deadline)
      await act(async () => { await new Promise(r => setTimeout(r, 20)); });
    assert.equal(document.querySelector("button")!.disabled, false, "recipient read settled");
  }
}
test("native recipient reader verifies independent originals and hides changed current contacts", async () => {
  const saved = globalThis.fetch, root = createRoot(document.getElementById("root")!), { campaign, contact, page } = await recipientFixture("push");
  let changed = false, corrupt = false; const calls: string[] = [];
  globalThis.fetch = async (url, options) => {
    assert.equal(new Headers(options?.headers).get("Authorization"), `Bearer ${token()}`);
    const path = String(url); calls.push(path);
    if (path.includes("recipient-observations?")) return reply(corrupt ? { ...page, total: 2 } : page);
    if (path.includes("contact-declarations")) return reply(changed && path.endsWith("/current") ? { ...contact, id: "new-current" } : contact);
    return reply(campaign);
  };
  try {
    setAccessToken(token()); await act(async () => root.render(<MarketingRecipientPanel institute="i" original={campaign} />));
    assert.equal(calls.length, 0); await click(); assert.equal(document.querySelectorAll("article").length, 1);
    assert.ok(calls.some(p => p.endsWith("/original/contact-key"))); assert.ok(calls.some(p => p.endsWith("/contact-declarations/contact")));
    assert.doesNotMatch(document.body.textContent!, /secret-token/);
    changed = true; await click(); assert.equal(document.querySelectorAll("article").length, 0); assert.ok(document.querySelector("[role=alert]"));
    changed = false; corrupt = true; await click(); assert.equal(document.querySelectorAll("article").length, 0);
    corrupt = false; await click(); assert.equal(document.querySelectorAll("article").length, 1);
    setAccessToken(token("reception", "accueil")); await act(async () => root.render(<MarketingRecipientPanel institute="i" original={campaign} />));
    assert.equal(document.querySelectorAll("article").length, 0); assert.equal(document.querySelector("button"), null);
  } finally { await act(async () => root.unmount()); globalThis.fetch = saved; }
});
test("late recipient response cannot populate another actor session", async () => {
  const saved = globalThis.fetch, root = createRoot(document.getElementById("root")!), { campaign, page } = await recipientFixture();
  let resolve!: (r: Response) => void; let calls = 0;
  globalThis.fetch = async () => { calls++; return new Promise(r => { resolve = r; }); };
  try {
    setAccessToken(token()); await act(async () => root.render(<MarketingRecipientPanel institute="i" original={campaign} />));
    await click(false); setAccessToken(token("new")); await act(async () => root.render(<MarketingRecipientPanel institute="i" original={campaign} />));
    await act(async () => resolve(reply(page))); assert.equal(calls, 1); assert.equal(document.querySelectorAll("article").length, 0);
  } finally { await act(async () => root.unmount()); globalThis.fetch = saved; }
});
