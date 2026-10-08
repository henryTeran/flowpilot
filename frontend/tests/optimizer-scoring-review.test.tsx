import test from "node:test";
import assert from "node:assert/strict";
import React, { act } from "react";
import { JSDOM } from "jsdom";
import fixture from "./fixtures/optimizer-review-16g.json";
import { OptimizerScoringReview } from "../src/components/OptimizerScoringReview";
import type { OptimizerReview } from "../src/optimizer-review-utils";
import { setAccessToken } from "../src/api/session";
const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (role = "responsable_institut", sub = "manager") => `h.${Buffer.from(JSON.stringify({ sub, role })).toString("base64url")}.s`;
const reply = (value: unknown) => new Response(JSON.stringify(value), { headers: { "Content-Type": "application/json" } });
const props = (value: unknown) => { const v = value as OptimizerReview; return { matching: { state: v.source.state, horizon_end: v.source.horizon_end, policy: v.source.policy }, policy: v.policy_original }; };
async function until(predicate: () => boolean) { for (let i = 0; i < 500 && !predicate(); i++) await act(async () => new Promise(r => setTimeout(r, 10))); assert.ok(predicate()); }
const button = () => document.querySelector<HTMLButtonElement>("button")!;
async function render(root: ReturnType<typeof createRoot>, value: unknown = fixture.options, extra: Partial<React.ComponentProps<typeof OptimizerScoringReview>> = {}) {
  await act(async () => root.render(<OptimizerScoringReview institute="own" timezone="Europe/Zurich" {...props(value)} {...extra} />));
}
async function load() { await until(() => !button().disabled); await act(async () => button().click()); await until(() => !document.querySelector('[role="status"]')); }

test("explicit current scoring pins complete selected references and displays exact score/factors/constraints", async () => {
  setAccessToken(token()); const root = createRoot(document.getElementById("root")!); let calls = 0;
  globalThis.fetch = async (url, init) => { calls++; assert.match(String(url), /optimizer\/institutes\/own\/reviews\/current$/); assert.equal(init?.method, "POST");
    const body = JSON.parse(init.body as string), v = fixture.options, latest = v.source.state.events.at(-1)!;
    assert.deepEqual(body, { policy_id: v.policy_original.original.id, policy_fingerprint: v.policy_original.fingerprint, root_id: v.source.state.root.original.id,
      expected_event_id: latest.original.id, expected_event_fingerprint: latest.fingerprint, horizon_end: v.source.horizon_end, matching_policy: v.source.policy }); return reply(v); };
  try {
    await render(root); await until(() => !button().disabled); assert.equal(calls, 0); assert.equal(document.activeElement, document.querySelector("section"));
    await load(); assert.equal(calls, 1); assert.equal(document.querySelectorAll("article").length, 1);
    assert.match(document.body.textContent!, /Classement complet/); assert.match(document.body.textContent!, /Score exact/); assert.match(document.body.textContent!, /Donnée inconnue/);
    assert.match(document.body.textContent!, /Ressources distinctes compatibles/); assert.match(document.body.textContent!, /Aucun créneau réservé/);
    assert.match(document.body.textContent!, /fenêtre capturée du/); assert.match(document.body.textContent!, /Devise du catalogue non enregistrée/);
    assert.doesNotMatch(document.querySelector("article")!.textContent!, /Quantité brute|microsecondes/);
    await render(root, fixture.options, { matching: undefined }); assert.equal(document.querySelector("article"), null); assert.equal(button().disabled, true); assert.equal(calls, 1);
  } finally { await act(async () => root.unmount()); }
});
test("weighted unknown and source refusal remain explicit; corrupt scores hide all old output and allow retry", async () => {
  setAccessToken(token()); const root = createRoot(document.getElementById("root")!); let value: unknown = fixture.revenue_score;
  globalThis.fetch = async () => reply(value);
  try {
    await render(root, value); await load(); assert.match(document.body.textContent!, /Classement indisponible/); assert.match(document.body.textContent!, /Score indisponible/);
    value = fixture.permission_refused; await render(root, value); await load(); assert.equal(document.querySelector("article"), null); assert.match(document.body.textContent!, /Accord de suivi insuffisant/);
    value = fixture.options; await render(root); await load(); assert.ok(document.querySelector("article"));
    const altered = structuredClone(fixture.options); altered.review!.options[0].score!.numerator = "999"; value = altered;
    await load(); assert.equal(document.querySelector("article"), null); assert.ok(document.querySelector('[role="alert"]'));
    value = fixture.options; await load(); assert.ok(document.querySelector("article")); assert.equal(document.querySelector('[role="alert"]'), null);
  } finally { await act(async () => root.unmount()); }
});
test("replaced policy, horizon or authority suppress late scores with no automatic request", async () => {
  setAccessToken(token()); const root = createRoot(document.getElementById("root")!); let resolve!: (r: Response) => void, calls = 0;
  globalThis.fetch = async () => { calls++; return new Promise<Response>(r => resolve = r); };
  try {
    await render(root); await until(() => !button().disabled); await act(async () => button().click());
    await render(root, fixture.delay); await act(async () => resolve(reply(fixture.options))); assert.equal(document.querySelector("article"), null); assert.equal(calls, 1);
    await until(() => !button().disabled); await act(async () => button().click());
    await render(root, fixture.delay, { matching: { ...props(fixture.delay).matching, horizon_end: "2030-01-01T12:00:00Z" } });
    await act(async () => resolve(reply(fixture.delay))); assert.equal(document.querySelector("article"), null); assert.equal(calls, 2);
    await until(() => !button().disabled); await act(async () => button().click()); setAccessToken(token("accueil"));
    await act(async () => resolve(reply(fixture.delay))); assert.equal(document.querySelector("article"), null); await render(root); assert.equal(document.querySelector("section"), null);
  } finally { await act(async () => root.unmount()); }
});
test("unverified or absent selections block scoring before HTTP", async () => {
  setAccessToken(token()); const root = createRoot(document.getElementById("root")!); let calls = 0; globalThis.fetch = async () => { calls++; return reply(fixture.options); };
  try {
    await render(root, fixture.options, { policy: undefined }); assert.equal(button().disabled, true);
    const bad = structuredClone(props(fixture.options).policy); bad.fingerprint = "0".repeat(64);
    await render(root, fixture.options, { policy: bad }); await until(() => !!document.querySelector('[role="alert"]')); assert.equal(button().disabled, true);
    await render(root, fixture.options, { matching: { ...props(fixture.options).matching, horizon_end: "2026-10-09" } });
    await until(() => !!document.querySelector('[role="alert"]')); assert.equal(button().disabled, true); assert.equal(calls, 0);
  } finally { await act(async () => root.unmount()); }
});
