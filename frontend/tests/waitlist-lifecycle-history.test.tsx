import test from "node:test";
import assert from "node:assert/strict";
import React, { act } from "react";
import { JSDOM } from "jsdom";
import fixture from "./fixtures/waitlist-lifecycle-15j.json";
import { WaitlistLifecycleHistory } from "../src/components/WaitlistLifecycleHistory";
import { setAccessToken } from "../src/api/session";
const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (role = "responsable_institut") => `h.${Buffer.from(JSON.stringify({ sub: "manager", role })).toString("base64url")}.s`;
const reply = (value: unknown) => new Response(JSON.stringify(value), { headers: { "Content-Type": "application/json" } });
async function read() {
  await act(async () => document.querySelector("button")!.click());
  for (let n = 0; n < 500 && document.querySelector<HTMLButtonElement>("button")!.disabled; n++) await act(async () => new Promise(r => setTimeout(r, 10)));
  assert.equal(document.querySelector<HTMLButtonElement>("button")!.disabled, false);
}
test("explicit lifecycle read presents verified causal actions and hides corrupted reread with retry", async () => {
  setAccessToken(token()); const root = createRoot(document.getElementById("root")!); let value: unknown = fixture.audit, reads = 0;
  globalThis.fetch = async (url, init) => { reads++; assert.equal(init?.method, "GET"); assert.match(String(url), /lifecycle\?offset=0&limit=20/); return reply(value); };
  try {
    await act(async () => root.render(<WaitlistLifecycleHistory institute="own" timezone="Europe/Zurich" />)); assert.equal(reads, 0);
    await read(); assert.equal(document.querySelectorAll("article").length, 2);
    assert.match(document.body.textContent!, /1 actives · 1 annulées/); assert.match(document.body.textContent!, /chaîne fermée/);
    assert.match(document.body.textContent!, /aucune nouvelle capture d’éligibilité/); assert.match(document.body.textContent!, /manager-É/);
    const headings = Array.from(document.querySelectorAll("article h4")).map(e => e.textContent); assert.deepEqual(headings.slice(0, 3), ["Activation", "Révision", "Annulation"]);
    assert.match(document.body.textContent!, new RegExp(fixture.cancelled.events[2].fingerprint));
    value = { ...fixture.audit, active: 2, cancelled: 0 }; await read(); assert.equal(document.querySelector("article"), null); assert.ok(document.querySelector('[role="alert"]'));
    value = fixture.audit; await read(); assert.equal(document.querySelectorAll("article").length, 2); assert.equal(document.querySelector('[role="alert"]'), null);
  } finally { await act(async () => root.unmount()); }
});
test("scope, timezone and authority changes reject late lifecycle replies without automatic I/O", async () => {
  setAccessToken(token()); const root = createRoot(document.getElementById("root")!); let release!: (response: Response) => void, reads = 0;
  globalThis.fetch = async () => { reads++; return new Promise<Response>(r => { release = r; }); };
  try {
    await act(async () => root.render(<WaitlistLifecycleHistory institute="own" timezone="UTC" />));
    await act(async () => document.querySelector("button")!.click());
    await act(async () => root.render(<WaitlistLifecycleHistory institute="other" timezone="UTC" />)); await act(async () => release(reply(fixture.audit)));
    assert.equal(document.querySelector("article"), null); assert.equal(reads, 1);
    await act(async () => root.render(<WaitlistLifecycleHistory institute="own" timezone="UTC" />)); await act(async () => document.querySelector("button")!.click());
    await act(async () => root.render(<WaitlistLifecycleHistory institute="own" timezone="Europe/Zurich" />)); await act(async () => release(reply(fixture.audit)));
    assert.equal(document.querySelector("article"), null); assert.equal(reads, 2);
    await act(async () => document.querySelector("button")!.click()); setAccessToken(token("accueil")); await act(async () => release(reply(fixture.audit)));
    assert.equal(document.querySelector("article"), null);
    await act(async () => root.render(<WaitlistLifecycleHistory institute="own" timezone="Europe/Zurich" />)); assert.equal(document.querySelector("section"), null);
  } finally { await act(async () => root.unmount()); }
});
