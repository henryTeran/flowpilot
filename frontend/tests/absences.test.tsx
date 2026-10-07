import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import React, { act } from "react";
import { AbsencePanel } from "../src/components/AbsencePanel";
import { validAbsence, validAbsenceIntent, matchesAbsence, type Absence } from "../src/absence-utils";
import { setAccessToken } from "../src/api/session";

const dom = new JSDOM("<!doctype html><div id='root'></div>", { url: "http://localhost:5173" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (role = "responsable_institut", sub = "manager") => `h.${Buffer.from(JSON.stringify({ role, sub })).toString("base64url")}.s`;
const response = (value: unknown) => new Response(JSON.stringify(value), { headers: { "Content-Type": "application/json" } });
const key = 'flowpilot.absence-request:["inst","manager"]';
const staff = [{ id: "emp", institute_id: "inst", first_name: "Angela", skills: [], status: "available" }];
function original(): Absence { return { id: "abs", institute_id: "inst", employee_id: "emp", kind: "leave",
  start_time: "2026-10-25T00:30:00Z", end_time: "2026-10-25T01:30:00Z", reason: "Congé confirmé",
  idempotency_key: "original", actor_id: "manager", created_at: "2026-10-07T01:00:00Z", cancellation: null }; }
const terms = () => { const { employee_id, kind, start_time, end_time, reason, idempotency_key } = original(); return { employee_id, kind, start_time, end_time, reason, idempotency_key }; };
function button(text: string) { return [...document.querySelectorAll<HTMLButtonElement>("button")].find(item => item.textContent === text)!; }

test("absence recovery validates institute, cancellation ownership, actor and actual repeated-hour instants", () => {
  assert.equal(validAbsence(original(), "inst"), true);
  assert.equal(validAbsenceIntent({ type: "create", terms: terms() }), true);
  assert.equal(matchesAbsence(original(), { ...terms(), start_time: "2026-10-25T02:30:00+02:00" }, "manager"), true);
  assert.equal(matchesAbsence(original(), { ...terms(), start_time: "2026-10-25T02:30:00+01:00" }, "manager"), false);
  assert.equal(matchesAbsence(original(), terms(), "other"), false);
  for (const change of [{ institute_id: "foreign" }, { end_time: original().start_time }, { actor_id: " " },
    { start_time: "2026-10-25T02:30:00" }, { cancellation: { id: "cancel", institute_id: "inst", absence_id: "other",
      actor_id: "manager", reason: "Return", idempotency_key: "return", created_at: "2026-10-07T01:00:00Z" } }]) {
    assert.equal(validAbsence({ ...original(), ...change }, "inst"), false);
  }
});

test("reception makes no sensitive absence read and manager hides corrupted fresh facts", async () => {
  const fetch = globalThis.fetch, root = createRoot(document.getElementById("root")!);
  let reads = 0, foreign = false;
  globalThis.fetch = async () => { reads++; return response([{ ...original(), institute_id: foreign ? "foreign" : "inst" }]); };
  try {
    sessionStorage.clear(); setAccessToken(token("accueil"));
    await act(async () => root.render(<AbsencePanel institute="inst" employees={staff} />)); assert.equal(reads, 0);
    setAccessToken(token()); await act(async () => root.render(<AbsencePanel institute="inst" employees={staff} timezone="Europe/Zurich" />));
    assert.match(document.querySelector(".absence-list")!.textContent!, /UTC\+02:00.*UTC\+01:00/);
    foreign = true; await act(async () => button("Actualiser les absences").click());
    assert.equal(document.querySelector(".absence-list"), null);
    assert.match(document.body.textContent!, /Lecture des absences à vérifier/);
    assert.equal(button("Enregistrer l’absence").closest("fieldset")!.disabled, true);
  } finally { await act(async () => root.unmount()); globalThis.fetch = fetch; }
});

test("saved original recovery sends no duplicate POST and retains request until planning refresh succeeds", async () => {
  const fetch = globalThis.fetch, root = createRoot(document.getElementById("root")!);
  let posts = 0, refreshed = false;
  globalThis.fetch = async (url, init) => { if (init?.method === "POST") posts++;
    return response(String(url).includes("/original/") ? original() : [original()]); };
  try {
    sessionStorage.clear(); setAccessToken(token()); sessionStorage.setItem(key, JSON.stringify({ type: "create", terms: terms() }));
    await act(async () => root.render(<AbsencePanel institute="inst" employees={staff} onChanged={async () => refreshed} />));
    await act(async () => button("Reprendre la demande d’absence conservée").click());
    assert.equal(posts, 0); assert.ok(sessionStorage.getItem(key)); assert.match(document.body.textContent!, /Actualisez le planning/);
    refreshed = true; await act(async () => button("Reprendre la demande d’absence conservée").click());
    assert.equal(posts, 0); assert.equal(sessionStorage.getItem(key), null); assert.match(document.body.textContent!, /Absence enregistrée/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = fetch; }
});

test("lost cancellation reply survives remount and recovers its original fact without another POST", async () => {
  const fetch = globalThis.fetch; let root = createRoot(document.getElementById("root")!);
  let posts = 0, cancellation: Absence["cancellation"] = null;
  const intent = { type: "cancel", absence_id: "abs", terms: { reason: "Retour", idempotency_key: "return" } };
  globalThis.fetch = async (url, init) => {
    const path = String(url);
    if (init?.method === "POST") { posts++; cancellation = { ...intent.terms, id: "cancel", institute_id: "inst", absence_id: "abs", actor_id: "manager", created_at: "2026-10-07T02:00:00Z" }; throw new Error("Réponse perdue"); }
    if (path.includes("/absence-cancellations/original/")) return response(cancellation);
    if (path.endsWith("/absences/abs")) return response({ ...original(), cancellation });
    return response([{ ...original(), cancellation }]);
  };
  try {
    sessionStorage.clear(); setAccessToken(token()); sessionStorage.setItem(key, JSON.stringify(intent));
    await act(async () => root.render(<AbsencePanel institute="inst" employees={staff} />));
    await act(async () => button("Reprendre la demande d’absence conservée").click()); assert.equal(posts, 1); assert.ok(sessionStorage.getItem(key));
    await act(async () => root.unmount()); root = createRoot(document.getElementById("root")!);
    await act(async () => root.render(<AbsencePanel institute="inst" employees={staff} />));
    await act(async () => button("Reprendre la demande d’absence conservée").click());
    assert.equal(posts, 1); assert.equal(sessionStorage.getItem(key), null); assert.match(document.body.textContent!, /Annulée : Retour/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = fetch; }
});

test("a late original read cannot issue a POST or clear the request after the signed actor changes", async () => {
  const fetch = globalThis.fetch, root = createRoot(document.getElementById("root")!);
  let release!: (value: Response) => void, posts = 0;
  globalThis.fetch = async (url, init) => {
    if (init?.method === "POST") posts++;
    if (String(url).includes("/original/")) return new Promise<Response>(resolve => { release = resolve; });
    return response([]);
  };
  try {
    sessionStorage.clear(); setAccessToken(token()); sessionStorage.setItem(key, JSON.stringify({ type: "create", terms: terms() }));
    await act(async () => root.render(<AbsencePanel institute="inst" employees={staff} />));
    await act(async () => { button("Reprendre la demande d’absence conservée").click(); await Promise.resolve(); });
    setAccessToken(token("responsable_institut", "new-manager"));
    await act(async () => root.render(<AbsencePanel institute="inst" employees={staff} />));
    await act(async () => release(response(null)));
    assert.equal(posts, 0); assert.ok(sessionStorage.getItem(key));
    assert.equal(button("Reprendre la demande d’absence conservée"), undefined);
  } finally { await act(async () => root.unmount()); globalThis.fetch = fetch; }
});
