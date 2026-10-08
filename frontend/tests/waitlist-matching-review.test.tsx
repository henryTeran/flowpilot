import test from "node:test";
import assert from "node:assert/strict";
import React, { act } from "react";
import { JSDOM } from "jsdom";
import fixture from "./fixtures/waitlist-matching-15l.json";
import { WaitlistMatchingReview } from "../src/components/WaitlistMatchingReview";
import { setAccessToken } from "../src/api/session";
import type { WaitlistLifecycleState } from "../src/waitlist-lifecycle-utils";
const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (role = "responsable_institut", sub = "manager") => `h.${Buffer.from(JSON.stringify({ sub, role })).toString("base64url")}.s`;
const reply = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { "Content-Type": "application/json" } });
function button(name: string) { const b = Array.from(document.querySelectorAll("button")).find(b => b.textContent === name); assert.ok(b, name); return b; }
async function until(predicate: () => boolean) { for (let n = 0; n < 500 && !predicate(); n++) await act(async () => new Promise(r => setTimeout(r, 10))); assert.ok(predicate()); }
async function settle() { await until(() => !document.querySelector('[role="status"]')); }
async function change(label: string, value: string) { await act(async () => {
  const wrapper = Array.from(document.querySelectorAll("label")).find(x => x.textContent!.startsWith(label)); assert.ok(wrapper, label);
  const input = wrapper.querySelector("input, select")! as HTMLInputElement | HTMLSelectElement;
  const proto = input.tagName === "SELECT" ? dom.window.HTMLSelectElement.prototype : dom.window.HTMLInputElement.prototype;
  Object.getOwnPropertyDescriptor(proto, "value")!.set!.call(input, value);
  input.dispatchEvent(new dom.window.Event(input.tagName === "SELECT" ? "change" : "input", { bubbles: true }));
}); }
async function configure() {
  await change("Fin de l’horizon — date", "2026-10-08"); await change("Fin de l’horizon — heure", "15:05");
  await change("Canal de suivi", "email"); await change("Règle d’historique", "review_only"); await change("Règle d’accord de suivi", "review_only");
}
async function click(name: string, wait = true) { await act(async () => button(name).click()); if (wait) await settle(); }
async function render(root: ReturnType<typeof createRoot>, props: Partial<React.ComponentProps<typeof WaitlistMatchingReview>> = {}) {
  await act(async () => root.render(<WaitlistMatchingReview institute="own" timezone="Europe/Zurich" {...props} />));
  if (props.selection && props.selection.state === "active" && (props.institute ?? "own") === "own") await until(() => document.body.textContent!.includes("Liste sélectionnée :"));
}
const selected = fixture.options.state as WaitlistLifecycleState;
test("explicit selected-version review requires empty policy/horizon choices, verifies pinned GET and hides corrupt proof with retry", async () => {
  setAccessToken(token()); const root = createRoot(document.getElementById("root")!); let value: unknown = fixture.options, calls = 0, reviewed: unknown;
  globalThis.fetch = async (url, init) => {
    calls++; assert.equal(init?.method, "GET"); const u = new URL(String(url));
    assert.match(u.pathname, /lifecycle\/states\/waitlist_demand_000\/matching$/);
    assert.equal(u.searchParams.get("horizon_end"), fixture.options.horizon_end.replace("Z", ".000Z"));
    assert.equal(u.searchParams.get("expected_event_id"), selected.events[1].original.id);
    assert.equal(u.searchParams.get("expected_event_fingerprint"), selected.events[1].fingerprint); return reply(value);
  };
  try {
    await render(root, { selection: selected, onReviewed: v => reviewed = v }); assert.equal(calls, 0); assert.equal(document.activeElement, document.querySelector("section"));
    assert.equal(button("Examiner la liste sélectionnée").disabled, true); await configure(); await click("Examiner la liste sélectionnée");
    assert.equal(document.querySelectorAll("article").length, 1); assert.match(document.body.textContent!, /Options conditionnelles/);
    assert.ok(reviewed);
    assert.match(document.body.textContent!, /aucun soin enregistré/); assert.match(document.body.textContent!, /inconnu — aucune déclaration/);
    const broken = structuredClone(fixture.options); broken.review!.options[0].resource_ids = ["room-flex", "room-flex"]; value = broken;
    await click("Examiner la liste sélectionnée"); assert.equal(document.querySelector("article"), null); assert.ok(document.querySelector('[role="alert"]'));
    assert.equal(reviewed, undefined);
    value = fixture.options; await click("Examiner la liste sélectionnée"); assert.ok(document.querySelector("article")); assert.equal(calls, 3);
    await change("Canal de suivi", "sms"); assert.equal(document.querySelector("article"), null); assert.equal(calls, 3);
    assert.equal(reviewed, undefined);
  } finally { await act(async () => root.unmount()); }
});
test("whole-waitlist detection reads twenty then five fresh conditional reviews and masks previous page on error", async () => {
  setAccessToken(token()); const root = createRoot(document.getElementById("root")!); const offsets: number[] = []; let corrupt = false;
  globalThis.fetch = async (url, init) => {
    assert.equal(init?.method, "GET"); const u = new URL(String(url)); assert.match(u.pathname, /\/detection$/);
    const offset = Number(u.searchParams.get("offset")); offsets.push(offset); assert.equal(u.searchParams.get("limit"), "20");
    return reply(corrupt ? { ...fixture.detection_20, active: 26 } : offset === 20 ? fixture.detection_20 : fixture.detection_0);
  };
  try {
    await render(root); assert.deepEqual(offsets, []); await configure(); await click("Détecter les créneaux des listes actives");
    assert.equal(document.querySelectorAll("article").length, 20); assert.match(document.body.textContent!, /24 listes avec options conditionnelles · 1 sans option/);
    await click("Détections suivantes"); assert.equal(document.querySelectorAll("article").length, 5); assert.match(document.body.textContent!, /21–25 sur 25/);
    await click("Détections précédentes"); assert.equal(document.querySelectorAll("article").length, 20);
    corrupt = true; await click("Détections suivantes"); assert.equal(document.querySelector("article"), null); assert.ok(document.querySelector('[role="alert"]'));
    assert.deepEqual(offsets, [0, 20, 0, 20]);
  } finally { await act(async () => root.unmount()); }
});
test("missing zone, skipped civil hour and repeated-hour occurrence never silently choose a horizon", async () => {
  setAccessToken(token()); const root = createRoot(document.getElementById("root")!); let calls = 0;
  globalThis.fetch = async () => { calls++; return reply(fixture.options); };
  try {
    await render(root, { timezone: undefined }); await configure(); assert.equal(button("Détecter les créneaux des listes actives").disabled, true);
    await render(root); await configure(); await change("Fin de l’horizon — date", "2026-03-29"); await change("Fin de l’horizon — heure", "02:30");
    assert.equal(button("Détecter les créneaux des listes actives").disabled, true); assert.match(document.body.textContent!, /inexistante ou invalide/);
    await change("Fin de l’horizon — date", "2026-10-25"); assert.equal(button("Détecter les créneaux des listes actives").disabled, true);
    const values = Array.from(document.querySelectorAll<HTMLSelectElement>("select")).find(x => x.parentElement!.textContent!.startsWith("Fin de l’horizon — occurrence"))!;
    assert.equal(values.options.length, 3); await change("Fin de l’horizon — occurrence", values.options[2].value);
    assert.equal(button("Détecter les créneaux des listes actives").disabled, false); await change("Fin de l’horizon — heure", "02:31");
    assert.equal(button("Détecter les créneaux des listes actives").disabled, true); assert.equal(calls, 0);
  } finally { await act(async () => root.unmount()); }
});
test("explicit history/permission refusals retain source explanation without presenting options", async () => {
  setAccessToken(token()); const root = createRoot(document.getElementById("root")!); let value: unknown = fixture.history_refused;
  globalThis.fetch = async () => reply(value);
  try {
    await render(root, { selection: selected }); await configure(); await change("Règle d’historique", "observed_care_required"); await click("Examiner la liste sélectionnée");
    assert.match(document.body.textContent!, /historique enregistré ne satisfait pas/); assert.match(document.body.textContent!, /Aucune option présentée/);
    value = fixture.permission_refused; await change("Règle d’historique", "review_only"); await change("Règle d’accord de suivi", "recorded_grant_required"); await click("Examiner la liste sélectionnée");
    assert.match(document.body.textContent!, /Aucun accord actuel enregistré/); assert.match(document.body.textContent!, /inconnu — aucune déclaration/);
  } finally { await act(async () => root.unmount()); }
});
test("scope, token, role, selected version and unmount changes suppress late source publication and old-session I/O", async () => {
  setAccessToken(token()); const root = createRoot(document.getElementById("root")!); let calls = 0, release!: (r: Response) => void, unmounted = false;
  globalThis.fetch = async () => { calls++; return new Promise<Response>(r => { release = r; }); };
  try {
    await render(root); await configure(); await click("Détecter les créneaux des listes actives", false);
    await render(root, { institute: "foreign" }); await act(async () => release(reply(fixture.detection_0))); assert.equal(document.querySelector("article"), null);
    await render(root); await configure(); await click("Détecter les créneaux des listes actives", false);
    setAccessToken(token("responsable_institut", "other")); await act(async () => release(reply(fixture.detection_0))); assert.equal(document.querySelector("article"), null);
    // A mounted old-session button must refuse even when no rerender preceded its click.
    await act(async () => button("Détecter les créneaux des listes actives").click()); assert.equal(calls, 2);
    setAccessToken(token()); await render(root, { selection: selected }); await configure(); await click("Examiner la liste sélectionnée", false);
    await render(root, { selection: fixture.cancelled.state as WaitlistLifecycleState }); await act(async () => release(reply(fixture.options)));
    assert.equal(document.querySelector("article"), null); assert.equal(button("Examiner la liste sélectionnée").disabled, true);
    setAccessToken(token("employee")); await render(root); assert.equal(document.querySelector("section"), null);
    setAccessToken(token()); await render(root); await configure(); await click("Détecter les créneaux des listes actives", false);
    await act(async () => root.unmount()); unmounted = true;
    await act(async () => release(reply(fixture.detection_0))); assert.equal(document.querySelector("article"), null);
  } finally { if (!unmounted) await act(async () => root.unmount()); }
});
