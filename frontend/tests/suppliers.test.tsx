import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import React, { act } from "react";
import { StockSuppliers } from "../src/components/StockSuppliers";
import { validSupplier, validSupplierIntent } from "../src/supplier-utils";
import { setAccessToken } from "../src/api/session";
const dom = new JSDOM("<!doctype html><div id='root'></div>", { url: "http://localhost:5173" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (sub = "manager", role = "responsable_institut") => `h.${Buffer.from(JSON.stringify({ sub, role })).toString("base64url")}.s`;
const response = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { "Content-Type": "application/json" } });
const intent = { reference: "SUP-1", name: "Cabine supplier", reason: "Approved identity", idempotency_key: "original" };
const supplier = { ...intent, id: "supplier", institute_id: "inst", actor_id: "manager", created_at: "2026-10-06T10:00:00Z" };
const key = `flowpilot.supplier-request:${JSON.stringify(["inst", "manager"])}`;
const panel = (institute = "inst") => <StockSuppliers institute={institute} />;
function button(name: string) { return Array.from(document.querySelectorAll<HTMLButtonElement>("button")).find(row => row.textContent === name)!; }

test("supplier identities reject foreign scope, forged or malformed original terms", () => {
  assert.equal(validSupplier(supplier, "inst"), true);
  for (const changed of [{ ...supplier, institute_id: "foreign" }, { ...supplier, reference: "bad spaces" }, { ...supplier, actor_id: "" }, { ...supplier, created_at: "2026-10-06T10:00:00" }, { ...supplier, name: " " }]) assert.equal(validSupplier(changed, "inst"), false);
  assert.equal(validSupplierIntent({ ...intent, reason: "x" }), false);
});

test("supplier reception is readonly and failed or wrong-scope refresh removes cached identities", async () => {
  sessionStorage.clear(); setAccessToken(token("staff", "collaboratrice"));
  const root = createRoot(document.getElementById("root")!), original = globalThis.fetch;
  let reads = 0, foreign = false;
  globalThis.fetch = async () => { reads++; return response([{ ...supplier, institute_id: foreign ? "foreign" : "inst" }]); };
  try {
    await act(async () => root.render(panel())); assert.equal(reads, 0);
    setAccessToken(token("cashier", "accueil")); await act(async () => root.render(panel()));
    assert.match(document.body.textContent!, /Cabine supplier/); assert.equal(document.querySelectorAll("form").length, 0);
    foreign = true; await act(async () => button("Actualiser les fournisseurs").click());
    assert.doesNotMatch(document.body.textContent!, /Cabine supplier/); assert.ok(document.querySelector('[role="alert"]'));
  } finally { await act(async () => root.unmount()); globalThis.fetch = original; }
});

test("lost supplier creation recovers the original key after reload and clears only after original and fresh reads", async () => {
  sessionStorage.clear(); setAccessToken(token()); sessionStorage.setItem(key, JSON.stringify(intent));
  let root = createRoot(document.getElementById("root")!), posts = 0, failedOriginal = true, failedList = false;
  const original = globalThis.fetch;
  globalThis.fetch = async (url, options) => {
    if (options?.method === "POST") { posts++; assert.deepEqual(JSON.parse(String(options.body)), intent); if (posts === 1) throw new Error("Lost reply"); return response(supplier); }
    if (String(url).endsWith("/supplier")) return failedOriginal ? response({ detail: "Original unavailable" }, 400) : response(supplier);
    if (failedList) throw new Error("List unavailable");
    return response(posts ? [supplier] : []);
  };
  try {
    await act(async () => root.render(panel())); await act(async () => button("Reprendre le fournisseur conservé").click());
    assert.ok(sessionStorage.getItem(key));
    await act(async () => root.unmount()); root = createRoot(document.getElementById("root")!);
    await act(async () => root.render(panel())); await act(async () => button("Reprendre le fournisseur conservé").click());
    assert.ok(sessionStorage.getItem(key)); assert.equal(button("Corriger la demande refusée"), undefined);
    failedOriginal = false; failedList = true; await act(async () => button("Reprendre le fournisseur conservé").click());
    assert.ok(sessionStorage.getItem(key));
    failedList = false; await act(async () => button("Actualiser les fournisseurs").click());
    await act(async () => button("Reprendre le fournisseur conservé").click());
    assert.equal(posts, 4); assert.equal(sessionStorage.getItem(key), null);
    assert.match(document.body.textContent!, /Fournisseur enregistré : Cabine supplier/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = original; sessionStorage.clear(); }
});

test("late prior-institute supplier write cannot publish or clear the original saved request", async () => {
  sessionStorage.clear(); setAccessToken(token()); sessionStorage.setItem(key, JSON.stringify(intent));
  const root = createRoot(document.getElementById("root")!), original = globalThis.fetch;
  let finish!: (value: Response) => void;
  globalThis.fetch = async (url, options) => options?.method === "POST" ? new Promise(resolve => { finish = resolve; }) : response([]);
  try {
    await act(async () => root.render(panel())); await act(async () => button("Reprendre le fournisseur conservé").click());
    setAccessToken(token("new-manager")); await act(async () => root.render(panel("new")));
    await act(async () => finish(response(supplier)));
    assert.ok(sessionStorage.getItem(key)); assert.doesNotMatch(document.body.textContent!, /Cabine supplier|Fournisseur enregistré/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = original; sessionStorage.clear(); }
});

test("an explicit creation rejection permits correcting the refused supplier request", async () => {
  sessionStorage.clear(); setAccessToken(token()); sessionStorage.setItem(key, JSON.stringify(intent));
  const root = createRoot(document.getElementById("root")!), original = globalThis.fetch;
  globalThis.fetch = async (url, options) => options?.method === "POST" ? response({ detail: "Duplicate reference" }, 400) : response([]);
  try {
    await act(async () => root.render(panel())); await act(async () => button("Reprendre le fournisseur conservé").click());
    assert.ok(sessionStorage.getItem(key)); await act(async () => button("Corriger la demande refusée").click());
    assert.equal(sessionStorage.getItem(key), null); assert.equal(document.querySelector<HTMLFieldSetElement>("fieldset")!.disabled, false);
    assert.equal(document.querySelector<HTMLInputElement>("input")!.value, intent.reference);
  } finally { await act(async () => root.unmount()); globalThis.fetch = original; sessionStorage.clear(); }
});
