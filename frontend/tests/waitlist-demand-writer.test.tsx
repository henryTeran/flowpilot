import test from "node:test";
import assert from "node:assert/strict";
import React, { act } from "react";
import { JSDOM } from "jsdom";
import fixture from "./fixtures/waitlist-originals-15g.json";
import { WaitlistDemandWriter } from "../src/components/WaitlistDemandWriter";
import { WaitlistPanel } from "../src/components/WaitlistPanel";
import { setAccessToken } from "../src/api/session";
import { waitlistIntentKey } from "../src/waitlist-intent";
import { revenueOriginalFingerprint } from "../src/revenue-scenario-utils";
import type { WaitlistRequest } from "../src/waitlist-original-utils";
import type { Employee, Service } from "../src/types";
const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (role = "responsable_institut") => `h.${Buffer.from(JSON.stringify({ sub: "manager", role })).toString("base64url")}.s`;
const key = waitlistIntentKey("own", "manager");
const services = [{ id: "care", name: "Soin", status: "active", duration_min: 30 }] as Service[];
const employees = [{ id: "employee", institute_id: "own", first_name: "Alice" }, { id: "foreign", institute_id: "other", first_name: "Foreign" }] as Employee[];
const customer = { id: "customer", institute_id: "own", display_name: "Cliente test", phone: null, created_at: "2026-10-05T10:00:00Z" };
const reply = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { "Content-Type": "application/json" } });
function button(name: string) { const value = Array.from(document.querySelectorAll("button")).find(b => b.textContent!.includes(name)); assert.ok(value, name); return value; }
async function click(name: string, settle = true) {
  await act(async () => button(name).click());
  if (settle) { for (let n = 0; n < 500 && document.querySelector('[role="status"]'); n++) await act(async () => new Promise(r => setTimeout(r, 10))); assert.equal(document.querySelector('[role="status"]'), null); }
}
function control(label: string) { const found = Array.from(document.querySelectorAll("label")).find(l => l.textContent!.startsWith(label))?.querySelector("input,textarea,select"); assert.ok(found, label); return found as HTMLInputElement; }
async function fill(label: string, value: string) {
  const input = control(label);
  await act(async () => { const proto = input.tagName === "TEXTAREA" ? dom.window.HTMLTextAreaElement.prototype : input.tagName === "SELECT" ? dom.window.HTMLSelectElement.prototype : dom.window.HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, "value")!.set!.call(input, value);
    input.dispatchEvent(new dom.window.Event(input.tagName === "SELECT" ? "change" : "input", { bubbles: true })); });
}
async function chooseCustomer() {
  await fill("Rechercher une cliente", "Cliente");
  await act(async () => new Promise(r => setTimeout(r, 260))); await click("Cliente test");
}
async function draft() {
  await chooseCustomer(); await fill("Prestation demandée", "care");
  await fill("Début disponibilité 1 — date", "2030-01-02"); await fill("Début disponibilité 1 — heure", "10:00");
  await fill("Fin disponibilité 1 — date", "2030-01-02"); await fill("Fin disponibilité 1 — heure", "12:00");
  await fill("Preuve des disponibilités", "Disponibilités déclarées 😀");
  await fill("Restriction de collaboratrices", "none"); await fill("Relecture des contraintes", "unknown");
  await fill("Motif de la demande", "Demande explicite de la cliente");
}
async function envelope(terms: WaitlistRequest) {
  const e = structuredClone(fixture.originals[0]);
  Object.assign(e.original, { actor_id: "manager", reason: terms.reason, idempotency_key: terms.idempotency_key });
  const { reason, idempotency_key, ...demand } = terms;
  Object.assign(e.original.demand, demand); Object.assign(e.original.source, { customer_id: terms.customer_id, service_id: terms.service_id, duration_minutes: terms.duration_minutes, allowed_employee_ids: terms.allowed_employee_ids });
  e.fingerprint = await revenueOriginalFingerprint(e.original); return e;
}
function render(root: ReturnType<typeof createRoot>, extra: Partial<React.ComponentProps<typeof WaitlistDemandWriter>> = {}) {
  return act(async () => root.render(<WaitlistDemandWriter institute="own" timezone="Europe/Zurich" services={services} employees={employees} {...extra} />));
}
test("native explicit multi-window declaration captures catalog duration and confirms independent receipt", async () => {
  sessionStorage.clear(); setAccessToken(token()); const root = createRoot(document.getElementById("root")!);
  let retained: unknown = null, calls = 0, posts = 0, callbacks = 0;
  globalThis.fetch = async (url, init) => { calls++; if (String(url).includes("/customers/")) return reply([customer]);
    if (init?.method === "POST") { posts++; const terms = JSON.parse(init.body as string);
      assert.deepEqual(JSON.parse(sessionStorage.getItem(key)!).terms, terms);
      assert.equal(terms.duration_minutes, 30); assert.equal(terms.availability.length, 2);
      assert.equal(terms.availability[0].start, "2030-01-02T09:00:00.000Z"); assert.equal(terms.constraints_evidence, null);
      assert.deepEqual(terms.allowed_employee_ids, ["employee"]); retained = await envelope(terms); }
    return reply(retained); };
  try {
    await render(root, { onRetained: () => callbacks++ }); assert.equal(calls, 0);
    await click("Conserver la demande"); assert.equal(calls, 0);
    await draft(); await fill("Restriction de collaboratrices", "selected");
    assert.doesNotMatch(document.body.textContent!, /Foreign/); await act(async () => document.querySelector<HTMLInputElement>('input[type="checkbox"]')!.click());
    await click("Ajouter une disponibilité");
    await fill("Début disponibilité 2 — date", "2030-01-03"); await fill("Début disponibilité 2 — heure", "09:00");
    await fill("Fin disponibilité 2 — date", "2030-01-03"); await fill("Fin disponibilité 2 — heure", "11:00");
    await click("Conserver la demande"); assert.equal(posts, 1); assert.equal(callbacks, 1); assert.equal(calls, 5);
    assert.match(document.body.textContent!, /Demande conservée et relue/); assert.match(document.body.textContent!, /activation à effectuer/);
    assert.equal(sessionStorage.getItem(key), null); assert.equal(document.querySelector("fieldset")!.disabled, true);
    await click("Déclarer une autre demande"); assert.equal(control("Prestation demandée").value, ""); assert.equal(control("Motif de la demande").value, "");
    assert.equal(control("Début disponibilité 1 — date").value, ""); assert.equal(control("Restriction de collaboratrices").value, "");
  } finally { await act(async () => root.unmount()); }
});
test("lost acknowledgement locks native draft and reload recovers once with same key", async () => {
  sessionStorage.clear(); setAccessToken(token()); let root = createRoot(document.getElementById("root")!);
  let retained: unknown = null, posts = 0, callbacks = 0;
  globalThis.fetch = async (url, init) => { if (String(url).includes("/customers/")) return reply([customer]);
    if (init?.method === "POST") { posts++; retained = await envelope(JSON.parse(init.body as string)); throw new TypeError("lost acknowledgement"); } return reply(retained); };
  try {
    await render(root); await draft(); await click("Conserver la demande"); assert.equal(posts, 1);
    assert.ok(sessionStorage.getItem(key)); assert.equal(document.querySelector("fieldset")!.disabled, true); assert.ok(document.querySelector('[role="alert"]'));
    await act(async () => root.unmount()); root = createRoot(document.getElementById("root")!);
    await render(root, { onRetained: () => callbacks++ }); await click("Reprendre la demande");
    assert.equal(posts, 1); assert.equal(callbacks, 1); assert.equal(sessionStorage.getItem(key), null);
    assert.match(document.body.textContent!, /Demande conservée et relue/);
  } finally { await act(async () => root.unmount()); }
});
test("institute DST skipped/repeated hours and missing catalog refuse before sending", async () => {
  sessionStorage.clear(); setAccessToken(token()); const root = createRoot(document.getElementById("root")!); let posts = 0;
  let retained: unknown = null;
  globalThis.fetch = async (url, init) => {
    if (init?.method === "POST") { posts++; const terms = JSON.parse(init.body as string);
      assert.equal(terms.availability[0].start, "2027-10-31T01:30:00.000Z"); retained = await envelope(terms); }
    return reply(String(url).includes("/customers/") ? [customer] : retained);
  };
  try {
    await render(root); await draft();
    await fill("Début disponibilité 1 — date", "2027-03-28"); await fill("Début disponibilité 1 — heure", "02:30");
    await fill("Fin disponibilité 1 — date", "2027-03-28"); await fill("Fin disponibilité 1 — heure", "04:00");
    await click("Conserver la demande"); assert.equal(posts, 0); assert.match(document.body.textContent!, /heure inexistante/);
    await fill("Début disponibilité 1 — date", "2027-10-31"); await fill("Fin disponibilité 1 — date", "2027-10-31");
    await click("Conserver la demande"); assert.equal(posts, 0); assert.ok(control("Début disponibilité 1 — occurrence"));
    await fill("Début disponibilité 1 — occurrence", "2027-10-31T01:30:00.000Z");
    await render(root, { services: [] }); await click("Conserver la demande"); assert.equal(posts, 0); assert.equal(sessionStorage.getItem(key), null);
    await render(root); await click("Conserver la demande"); assert.equal(posts, 1);
    assert.match(document.body.textContent!, /Demande conservée et relue/);
  } finally { await act(async () => root.unmount()); }
});
test("confirmed authoring invalidates prior history without an automatic reread", async () => {
  sessionStorage.clear(); setAccessToken(token()); const root = createRoot(document.getElementById("root")!);
  const { institute_id, declared_at, ...demand } = fixture.originals[0].original.demand;
  const terms = { ...demand, reason: fixture.originals[0].original.reason, idempotency_key: fixture.originals[0].original.idempotency_key } as WaitlistRequest;
  sessionStorage.setItem(key, JSON.stringify({ institute: "own", actor: "manager", terms }));
  const retained = await envelope(terms); let audits = 0;
  globalThis.fetch = async url => { if (String(url).includes("?offset=")) { audits++; return reply(fixture); } return reply(retained); };
  try {
    await act(async () => root.render(<WaitlistPanel institute="own" timezone="Europe/Zurich" services={services} employees={employees} />));
    await click("Lire les demandes conservées");
    const history = () => document.querySelector('[aria-label="Demandes de liste d’attente conservées"]')!;
    assert.equal(history().querySelectorAll("article").length, 1);
    await click("Reprendre la demande"); assert.equal(history().querySelectorAll("article").length, 0); assert.equal(audits, 1);
    await click("Lire les demandes conservées"); assert.equal(audits, 2); assert.equal(history().querySelectorAll("article").length, 1);
  } finally { await act(async () => root.unmount()); }
});
test("definitive native rejection enables correction only after fresh key check", async () => {
  sessionStorage.clear(); setAccessToken(token()); const root = createRoot(document.getElementById("root")!); let keyReads = 0;
  globalThis.fetch = async (url, init) => { if (String(url).includes("/customers/")) return reply([customer]);
    if (init?.method === "POST") return reply({ detail: "source changed" }, 422); keyReads++; return reply(null); };
  try {
    await render(root); await draft(); await click("Conserver la demande"); assert.equal(document.querySelector("fieldset")!.disabled, true);
    await click("Vérifier la clé avant correction"); assert.equal(keyReads, 2); assert.equal(sessionStorage.getItem(key), null);
    assert.equal(document.querySelector("fieldset")!.disabled, false);
  } finally { await act(async () => root.unmount()); }
});
test("invalid local intent and unavailable timezone/role prevent new native writes", async () => {
  sessionStorage.clear(); setAccessToken(token()); sessionStorage.setItem(key, "broken"); const root = createRoot(document.getElementById("root")!); let calls = 0;
  globalThis.fetch = async () => { calls++; return reply(null); };
  try {
    await render(root); assert.equal(button("Conserver la demande").disabled, true); assert.match(document.body.textContent!, /locale est illisible/);
    sessionStorage.removeItem(key); await render(root, { timezone: "Invalid/Zone" }); assert.equal(button("Conserver la demande").disabled, true);
    setAccessToken(token("accueil")); await render(root); assert.equal(document.querySelector("section"), null); assert.equal(calls, 0);
  } finally { await act(async () => root.unmount()); }
});
test("scope/session changes suppress late native receipt and preserve original recovery", async () => {
  sessionStorage.clear(); setAccessToken(token()); const root = createRoot(document.getElementById("root")!); let release!: (r: Response) => void, posts = 0, callbacks = 0;
  globalThis.fetch = async (url, init) => { if (String(url).includes("/customers/")) return reply([customer]);
    if (init?.method === "POST") { posts++; return reply(null); } return new Promise<Response>(r => { release = r; }); };
  try {
    await render(root, { onRetained: () => callbacks++ }); await draft(); await click("Conserver la demande", false);
    await render(root, { institute: "other", onRetained: () => callbacks++ }); await act(async () => release(reply(null)));
    assert.equal(posts, 0); assert.equal(callbacks, 0); assert.ok(sessionStorage.getItem(key));
    await render(root); await click("Reprendre la demande", false); setAccessToken(token("accueil")); await act(async () => release(reply(null)));
    assert.equal(posts, 0); assert.equal(callbacks, 0); assert.ok(sessionStorage.getItem(key));
  } finally { await act(async () => root.unmount()); }
});
