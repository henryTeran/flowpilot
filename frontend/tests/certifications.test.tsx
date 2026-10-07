import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import React, { act } from "react";
import { CertificationPanel, CertificationReadOnly } from "../src/components/CertificationPanel";
import { certificationInstant, validCertificationPage, matchesCertification, type Certification, type CertificationPage } from "../src/certification-utils";
import { setAccessToken } from "../src/api/session";
const dom = new JSDOM("<!doctype html><div id='root'></div>", { url: "http://localhost:5173" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (role = "responsable_institut", sub = "manager") => `h.${Buffer.from(JSON.stringify({ role, sub })).toString("base64url")}.s`;
const response = (value: unknown) => new Response(JSON.stringify(value), { headers: { "Content-Type": "application/json" } });
const storage = 'flowpilot.certification-request:["inst","manager"]';
const staff = [{ id: "emp", institute_id: "inst", first_name: "Angela", skills: [], status: "available" }];
function original(): Certification { return { id: "cert", institute_id: "inst", employee_id: "emp", code: "CREDENTIAL", title: "Recorded course", issuer: "Declared issuer", reference: "REF-26", issued_on: null,
  valid_from: "2026-10-07T12:00:00.000001Z", valid_until: "2026-10-07T12:00:00.000003Z", reason: "Original declaration", idempotency_key: "original", actor_id: "manager", created_at: "2026-10-07T11:00:00Z", revocation: null }; }
function page(certificate = original()): CertificationPage { return { institute_id: "inst", employee_id: "emp", generated_at: "2026-10-07T12:00:00.000002Z", page: { offset: 0, limit: 50, total: 1 }, rows: [{ certificate, state: certificate.revocation ? "revoked" : "in_validity_window" }] }; }
function terms() { const { employee_id, code, title, issuer, reference, issued_on, valid_from, valid_until, reason, idempotency_key } = original(); return { employee_id, code, title, issuer, reference, issued_on, valid_from, valid_until, reason, idempotency_key }; }
const button = (label: string) => [...document.querySelectorAll<HTMLButtonElement>("button")].find(row => row.textContent === label)!;

test("certification readings preserve microseconds, declared expiry, ownership and nullable provenance", () => {
  assert.equal(validCertificationPage(page(), "inst", "emp", 0), true);
  assert.equal(certificationInstant("2026-10-07T14:00:00.000001+02:00"), certificationInstant(original().valid_from));
  assert.equal(certificationInstant("0001-01-01T00:00:00+14:00"), undefined);
  assert.equal(certificationInstant("2026-02-30T00:00:00Z"), undefined);
  assert.equal(matchesCertification(original(), { ...terms(), valid_from: "2026-10-07T12:00:00.000002Z" }, "manager"), false);
  const corruptions = [
    (row: CertificationPage) => { row.rows[0].state = "expired"; }, (row: CertificationPage) => { row.employee_id = "foreign"; },
    (row: CertificationPage) => { row.page.total = 2; }, (row: CertificationPage) => { row.rows[0].certificate.actor_id = " "; },
    (row: CertificationPage) => { row.rows[0].certificate.issued_on = "2026-02-30"; },
    (row: CertificationPage) => { row.rows[0].certificate.revocation = { id: "rev", institute_id: "inst", certification_id: "foreign", reason: "Correction", idempotency_key: "revoke", actor_id: "manager", created_at: "2026-10-07T12:00:00Z" }; row.rows[0].state = "revoked"; },
  ];
  for (const corrupt of corruptions) { const value = page(); corrupt(value); assert.equal(validCertificationPage(value, "inst", "emp", 0), false); }
});

test("readonly profile refuses reception, exposes declared provenance and masks contradictory fresh state", async () => {
  const fetch = globalThis.fetch, root = createRoot(document.getElementById("root")!); let reads = 0, corrupt = false;
  globalThis.fetch = async () => { reads++; const value = page(); if (corrupt) value.rows[0].state = "expired"; return response(value); };
  try {
    sessionStorage.clear(); setAccessToken(token("accueil")); await act(async () => root.render(<CertificationReadOnly institute="inst" employee="emp" />)); assert.equal(reads, 0);
    setAccessToken(token()); await act(async () => root.render(<CertificationReadOnly institute="inst" employee="emp" />));
    assert.match(document.body.textContent!, /Période déclarée en cours/); assert.match(document.body.textContent!, /Date d’émission : Non connue/);
    assert.equal(document.querySelector("form"), null); corrupt = true; await act(async () => button("Actualiser les certifications").click());
    assert.equal(document.querySelector("li"), null); assert.match(document.body.textContent!, /Lecture des certifications à vérifier/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = fetch; }
});

test("original certification recovery verifies the immutable terms before clearing a saved request without POST", async () => {
  const fetch = globalThis.fetch, root = createRoot(document.getElementById("root")!); let posts = 0, changed = true;
  globalThis.fetch = async (url, init) => { if (init?.method === "POST") posts++;
    if (String(url).includes("/original/")) return response({ ...original(), reference: changed ? "wrong" : original().reference }); return response(page()); };
  try {
    sessionStorage.clear(); setAccessToken(token()); sessionStorage.setItem(storage, JSON.stringify({ type: "create", terms: terms() }));
    await act(async () => root.render(<CertificationPanel institute="inst" employees={staff} />));
    await act(async () => button("Reprendre la demande de certification conservée").click());
    assert.ok(sessionStorage.getItem(storage)); assert.equal(posts, 0); assert.match(document.body.textContent!, /originale à vérifier/);
    changed = false; await act(async () => button("Reprendre la demande de certification conservée").click());
    assert.equal(posts, 0); assert.equal(sessionStorage.getItem(storage), null); assert.match(document.body.textContent!, /Certification enregistrée/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = fetch; }
});

test("a lost revocation reply survives remount and recovers the single original fact", async () => {
  const fetch = globalThis.fetch; let root = createRoot(document.getElementById("root")!); let certificate = original(), posts = 0;
  const intent = { type: "revoke", employee_id: "emp", certification_id: "cert", terms: { reason: "Correction document", idempotency_key: "revoke" } };
  globalThis.fetch = async (url, init) => { const path = String(url);
    if (init?.method === "POST") { posts++; certificate = { ...certificate, revocation: { ...intent.terms, id: "rev", institute_id: "inst", certification_id: "cert", actor_id: "manager", created_at: "2026-10-07T12:00:00.000004Z" } }; throw new Error("Lost reply"); }
    if (path.includes("/certification-revocations/original/")) return response(certificate.revocation);
    if (path.endsWith("/certifications/cert")) return response(certificate); return response(page(certificate));
  };
  try {
    sessionStorage.clear(); setAccessToken(token()); sessionStorage.setItem(storage, JSON.stringify(intent));
    await act(async () => root.render(<CertificationPanel institute="inst" employees={staff} />));
    await act(async () => button("Reprendre la demande de certification conservée").click()); assert.equal(posts, 1); assert.ok(sessionStorage.getItem(storage));
    await act(async () => root.unmount()); root = createRoot(document.getElementById("root")!);
    await act(async () => root.render(<CertificationPanel institute="inst" employees={staff} />));
    await act(async () => button("Reprendre la demande de certification conservée").click());
    assert.equal(posts, 1); assert.equal(sessionStorage.getItem(storage), null); assert.match(document.body.textContent!, /Certification révoquée/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = fetch; }
});

test("late old actor recovery cannot issue a POST or clear another actor's request", async () => {
  const fetch = globalThis.fetch, root = createRoot(document.getElementById("root")!); let posts = 0, release!: (response: Response) => void;
  globalThis.fetch = async (url, init) => { if (init?.method === "POST") posts++;
    return String(url).includes("/original/") ? new Promise(resolve => { release = resolve; }) : response(page()); };
  try {
    sessionStorage.clear(); setAccessToken(token()); sessionStorage.setItem(storage, JSON.stringify({ type: "create", terms: terms() }));
    await act(async () => root.render(<CertificationPanel institute="inst" employees={staff} />));
    await act(async () => { button("Reprendre la demande de certification conservée").click(); await Promise.resolve(); });
    setAccessToken(token("responsable_institut", "new-manager")); await act(async () => root.render(<CertificationPanel institute="inst" employees={staff} />));
    await act(async () => release(response(null))); assert.equal(posts, 0); assert.ok(sessionStorage.getItem(storage));
    assert.equal(button("Reprendre la demande de certification conservée"), undefined);
  } finally { await act(async () => root.unmount()); globalThis.fetch = fetch; }
});
