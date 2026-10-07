import test from "node:test";
import assert from "node:assert/strict";
import React, { act } from "react";
import { JSDOM } from "jsdom";
import { readFileSync } from "node:fs";
import { MarketingConversionWriter } from "../src/components/MarketingConversionWriter";
import { attributionFingerprint, type ConversionOriginal } from "../src/marketing-conversion-utils";
import { setAccessToken } from "../src/api/session";
const v = JSON.parse(readFileSync(new URL("./fixtures/marketing-conversions-13bb.json", import.meta.url), "utf8"));
const a = v.linked.attribution, institute = v.institute_id;
const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = () => `h.${Buffer.from(JSON.stringify({ sub: "manager", role: "responsable_institut" })).toString("base64url")}.s`;
const reply = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { "Content-Type": "application/json" } });
async function click(label: string) {
  await act(async () => [...document.querySelectorAll("button")].find(b => b.textContent === label)!.click());
  for (let n = 0; n < 200 && document.querySelector('[role="status"]'); n++) await act(async () => { await new Promise(r => setTimeout(r, 10)); });
}
async function reason(value: string) {
  await act(async () => {
    const input = document.querySelector("input")!;
    Object.getOwnPropertyDescriptor(dom.window.HTMLInputElement.prototype, "value")!.set!.call(input, value);
    input.dispatchEvent(new dom.window.Event("input", { bubbles: true })); input.dispatchEvent(new dom.window.Event("change", { bubbles: true }));
  });
}
const component = () => <MarketingConversionWriter institute={institute} intent={a.intent} accepted={a.accepted} ticket={a.ticket.ticket_id} period={a.window} />;
function server(options: { lost?: boolean; rejected?: boolean; corrupt?: boolean; initial?: ConversionOriginal } = {}) {
  let original: ConversionOriginal | null = null, head = options.initial || null, posts = 0, reads = 0;
  globalThis.fetch = async (url, init) => {
    reads++; const path = String(url);
    if (init?.method === "POST") {
      posts++; const request = JSON.parse(String(init.body));
      assert.ok([...Array(sessionStorage.length)].some((_, i) => sessionStorage.key(i)?.startsWith("flowpilot.conversion-request:")));
      if (options.rejected) return reply({ detail: "Explicit fixture refusal" }, 400);
      original = structuredClone(v.linked); original!.id = `native-original-${posts}`; original!.request = request;
      if (request.action === "retracted") original!.attribution = structuredClone(head!.attribution);
      else { original!.attribution.reason = request.reason; original!.attribution.idempotency_key = request.idempotency_key; }
      original!.attribution_fingerprint = await attributionFingerprint(original!.attribution); head = original;
      if (options.lost) { options.lost = false; throw new TypeError("Lost reply"); }
      return reply(original);
    }
    if (path.includes("/conversions/")) {
      if (path.endsWith("/current")) return reply(head);
      if (path.includes("/original/")) return reply(original && path.endsWith(original.request.idempotency_key) ? original
        : head && path.endsWith(head.request.idempotency_key) ? head : null);
      return reply(options.corrupt && original ? { ...original, attribution_fingerprint: "0".repeat(64) } : original || head);
    }
    if (path.includes("/campaigns/")) return reply(a.authorization);
    if (path.includes("/outcomes/")) return reply(a.accepted);
    return reply(a.intent);
  };
  return { posts: () => posts, reads: () => reads };
}
test("lost acknowledgement freezes terms and reload recovers exact original with one POST", async () => {
  sessionStorage.clear(); setAccessToken(token()); let root = createRoot(document.getElementById("root")!);
  const s = server({ lost: true });
  try {
    await act(async () => root.render(component())); assert.equal(s.reads(), 0);
    await click("Vérifier le lien courant"); await reason("Explicit native link"); await click("Enregistrer le lien de conversion");
    assert.equal(s.posts(), 1); assert.ok(document.querySelector('[role="alert"]'));
    assert.equal(document.querySelector("input")!.disabled, true);
    await act(async () => root.unmount()); root = createRoot(document.getElementById("root")!);
    await act(async () => root.render(component()));
    await click("Récupérer ou réessayer la même opération");
    assert.equal(s.posts(), 1); assert.match(document.body.textContent!, /Lien enregistré/);
    assert.equal([...Array(sessionStorage.length)].filter((_, i) => sessionStorage.key(i)?.startsWith("flowpilot.conversion-request:")).length, 0);
    await click("Nouvelle décision pour ce ticket");
    assert.equal(document.querySelector("input")!.disabled, false);
    await click("Vérifier le lien courant"); await reason("Explicit subsequent exclusion"); await click("Rétracter le lien courant");
    assert.equal(s.posts(), 2); assert.match(document.body.textContent!, /Lien rétracté/);
  } finally { await act(async () => root.unmount()); }
});
test("retraction selects exact current head and preserves its historical attribution", async () => {
  sessionStorage.clear(); setAccessToken(token()); const root = createRoot(document.getElementById("root")!);
  const s = server({ initial: v.linked });
  try {
    await act(async () => root.render(component())); await click("Vérifier le lien courant");
    await reason("Explicit native exclusion"); await click("Rétracter le lien courant");
    assert.equal(s.posts(), 1); assert.match(document.body.textContent!, /Lien rétracté/);
    assert.equal(document.querySelector('[role="alert"]'), null);
  } finally { await act(async () => root.unmount()); }
});
test("independent receipt mismatch keeps protected terms; definitive rejection requires key-first correction", async () => {
  sessionStorage.clear(); setAccessToken(token()); let root = createRoot(document.getElementById("root")!);
  let s = server({ corrupt: true });
  try {
    await act(async () => root.render(component())); await click("Vérifier le lien courant"); await reason("Explicit native link");
    await click("Enregistrer le lien de conversion"); assert.equal(s.posts(), 1);
    assert.ok(document.querySelector('[role="alert"]')); assert.doesNotMatch(document.body.textContent!, /Lien enregistré/);
    assert.equal(document.querySelector("input")!.disabled, true);
    await act(async () => root.unmount()); sessionStorage.clear(); setAccessToken(token()); root = createRoot(document.getElementById("root")!);
    s = server({ rejected: true });
    await act(async () => root.render(component())); await click("Vérifier le lien courant"); await reason("Explicit refused link");
    await click("Enregistrer le lien de conversion"); await click("Corriger après le refus");
    assert.equal(s.posts(), 1); assert.equal(document.querySelector("input")!.disabled, false);
    assert.match(document.body.textContent!, /Vérifier le lien courant/);
  } finally { await act(async () => root.unmount()); }
});
