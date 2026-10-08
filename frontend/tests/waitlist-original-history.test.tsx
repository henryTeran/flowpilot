import test from "node:test";
import assert from "node:assert/strict";
import React, { act } from "react";
import { JSDOM } from "jsdom";
import { readFileSync } from "node:fs";
import { WaitlistOriginalHistory } from "../src/components/WaitlistOriginalHistory";
import { setAccessToken } from "../src/api/session";
const fixture = JSON.parse(readFileSync(new URL("./fixtures/waitlist-originals-15g.json", import.meta.url), "utf8"));
const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (role = "responsable_institut") => `h.${Buffer.from(JSON.stringify({ sub: "manager", role })).toString("base64url")}.s`;
const reply = (value: unknown) => new Response(JSON.stringify(value), { headers: { "Content-Type": "application/json" } });
async function readAndSettle() {
  await act(async () => document.querySelector("button")!.click());
  for (let n = 0; n < 500 && document.querySelector<HTMLButtonElement>("button")!.disabled; n++) {
    await act(async () => new Promise(resolve => setTimeout(resolve, 10)));
  }
  assert.equal(document.querySelector<HTMLButtonElement>("button")!.disabled, false);
}

test("explicit history read verifies retained declaration, masks corrupted proof and allows retry", async () => {
  setAccessToken(token()); const root = createRoot(document.getElementById("root")!); let reads = 0, value: unknown = fixture;
  globalThis.fetch = async (url, init) => { reads++; assert.equal(init?.method, "GET");
    assert.match(String(url), /waitlist\/institutes\/own\/originals\?offset=0&limit=20/); return reply(value); };
  try {
    await act(async () => root.render(<WaitlistOriginalHistory institute="own" timezone="Europe/Zurich" />));
    assert.equal(reads, 0);
    await readAndSettle();
    assert.ok(document.querySelector("article")); assert.match(document.body.textContent!, /manager-É/);
    assert.match(document.body.textContent!, /ne prouve ni activation/);
    value = { ...fixture, basis: "active_waitlist" };
    await readAndSettle();
    assert.equal(document.querySelector("article"), null); assert.ok(document.querySelector("[role=alert]"));
    value = fixture; await readAndSettle();
    assert.ok(document.querySelector("article")); assert.equal(document.querySelector("[role=alert]"), null);
  } finally { await act(async () => root.unmount()); }
});

test("changed institute and authority invalidate late history replies without automatic reads", async () => {
  setAccessToken(token()); const root = createRoot(document.getElementById("root")!); let resolve!: (response: Response) => void, reads = 0;
  globalThis.fetch = async () => { reads++; return new Promise<Response>(r => { resolve = r; }); };
  try {
    await act(async () => root.render(<WaitlistOriginalHistory institute="own" timezone="UTC" />));
    await act(async () => document.querySelector("button")!.click());
    await act(async () => root.render(<WaitlistOriginalHistory institute="other" timezone="UTC" />));
    await act(async () => resolve(reply(fixture)));
    assert.equal(document.querySelector("article"), null); assert.equal(reads, 1);
    await act(async () => root.render(<WaitlistOriginalHistory institute="own" timezone="UTC" />));
    await act(async () => document.querySelector("button")!.click());
    setAccessToken(token("accueil"));
    await act(async () => resolve(reply(fixture)));
    assert.equal(document.querySelector("article"), null);
    await act(async () => root.render(<WaitlistOriginalHistory institute="own" timezone="UTC" />));
    assert.equal(document.querySelector("section"), null);
  } finally { await act(async () => root.unmount()); }
});
