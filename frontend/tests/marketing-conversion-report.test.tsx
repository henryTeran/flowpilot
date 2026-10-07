import test from "node:test";
import assert from "node:assert/strict";
import React, { act } from "react";
import { JSDOM } from "jsdom";
import { readFileSync } from "node:fs";
import { MarketingConversionReport } from "../src/components/MarketingConversionReport";
import { setAccessToken } from "../src/api/session";
const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const v = JSON.parse(readFileSync(new URL("./fixtures/marketing-conversions-13bb.json", import.meta.url), "utf8"));
const token = (role = "responsable_institut") => `h.${Buffer.from(JSON.stringify({ sub: "manager", role })).toString("base64url")}.s`;
const reply = (value: unknown) => new Response(JSON.stringify(value), { headers: { "Content-Type": "application/json" } });
async function input(index: number, value: string) {
  const element = document.querySelectorAll("input")[index];
  await act(async () => {
    Object.getOwnPropertyDescriptor(dom.window.HTMLInputElement.prototype, "value")!.set!.call(element, value);
    element.dispatchEvent(new dom.window.Event("input", { bubbles: true }));
    element.dispatchEvent(new dom.window.Event("change", { bubbles: true }));
  });
}
async function click() { await act(async () => document.querySelector("button")!.click()); }
test("explicit report read preserves exact money, hides invalid reports and denies non-manager", async () => {
  setAccessToken(token()); const root = createRoot(document.getElementById("root")!);
  let calls = 0, corrupt = false;
  globalThis.fetch = async () => { calls++; return reply(corrupt ? { ...v.report, full_retained_current_cohort: 1 } : v.report); };
  try {
    await act(async () => root.render(<MarketingConversionReport institute={v.institute_id} campaign={v.campaign_id} />));
    assert.equal(calls, 0);
    await click(); assert.equal(calls, 0); assert.ok(document.querySelector('[role="alert"]'));
    await input(0, v.window.start); await input(1, v.window.end); await click();
    assert.equal(calls, 1); assert.match(document.body.textContent!, /123\.45 CHF/);
    corrupt = true; await click(); assert.ok(document.querySelector('[role="alert"]'));
    assert.doesNotMatch(document.body.textContent!, /123\.45 CHF/);
    setAccessToken(token("accueil"));
    await act(async () => root.render(<MarketingConversionReport institute={v.institute_id} campaign={v.campaign_id} />));
    assert.equal(document.querySelector("button"), null);
  } finally { await act(async () => root.unmount()); }
});
test("period edits and signed session changes discard an outstanding report", async () => {
  setAccessToken(token()); const root = createRoot(document.getElementById("root")!);
  let resolve: (r: Response) => void = () => {};
  globalThis.fetch = () => new Promise<Response>(r => { resolve = r; });
  try {
    await act(async () => root.render(<MarketingConversionReport institute={v.institute_id} campaign={v.campaign_id} />));
    await input(0, v.window.start); await input(1, v.window.end); await click();
    await input(0, "2026-10-08T12:00:00Z");
    await act(async () => resolve(reply(v.report)));
    assert.doesNotMatch(document.body.textContent!, /123\.45 CHF/);
    await input(0, v.window.start); await click(); setAccessToken(token("accueil"));
    await act(async () => resolve(reply(v.report)));
    assert.doesNotMatch(document.body.textContent!, /123\.45 CHF/);
  } finally { await act(async () => root.unmount()); }
});
