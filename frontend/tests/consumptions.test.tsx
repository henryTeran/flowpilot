import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import React, { act } from "react";
import { StockConsumptions } from "../src/components/StockConsumptions";
import { validWorkDetail, validConsumption, type ConsumptionIntent } from "../src/consumption-utils";
import { setAccessToken } from "../src/api/session";
const dom = new JSDOM("<!doctype html><div id='root'></div>", { url: "http://localhost:5173" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (sub = "manager", role = "responsable_institut") => `h.${Buffer.from(JSON.stringify({ sub, role })).toString("base64url")}.s`;
const response = (value: unknown) => new Response(JSON.stringify(value), { headers: { "Content-Type": "application/json" } });
const expected = [{ item_id: "stock", quantity: "4.125", unit: "ml" as const }];
const work = { billing_state: "active", invoice_removed_at: null, employee_name: "Angela", ticket_number: "BM-001", basis_id: "basis", institute_id: "inst", source_kind: "sessions", source_id: "session", source_status: "completed", service_id: "care", service_name: "Care", quantity: 1, state: "enabled", captured_at: "2026-10-06T10:00:00Z", completed_at: "2026-10-06T10:30:00Z", consumption_id: null };
const actual = { id: "actual", institute_id: "inst", basis_id: "basis", actor_id: "manager", reason: "Actual measured quantity", idempotency_key: "original", entries: [{ ...expected[0], movement_id: "move" }], expected_entries: expected, matches_norm: true, created_at: "2026-10-06T11:00:00Z" };
const detail = { ...work, expected_entries: expected, consumption: null };
const item = { id: "stock", institute_id: "inst", sku: "SERUM", name: "Serum", category: "cabine", unit: "ml", reorder_threshold: "1.000", on_hand: "10.125", at_or_below_threshold: false, actor_id: "manager", created_at: "2026-10-06T10:00:00Z" };
const intent: ConsumptionIntent = { basis_name: "Care", basis_state: "enabled", expected_entries: expected, no_material: false, entries: [{ ...expected[0], name: "Serum", sku: "SERUM" }], reason: actual.reason, idempotency_key: "original" };
const key = `flowpilot.consumption-request:${JSON.stringify(["inst", "basis", "manager"])}`;
function button(text: string) { return Array.from(document.querySelectorAll<HTMLButtonElement>("button")).find(button => button.textContent === text)!; }
async function open() { await act(async () => document.querySelector<HTMLButtonElement>(".bm-stock-grid button")!.click()); }
const panel = (refresh = async () => true, institute = "inst") => <StockConsumptions institute={institute} onStockRefresh={refresh} />;


test("actual and work snapshots reject changed norm comparison, foreign scope and missing linked identity", () => {
  assert.equal(validWorkDetail(detail, "inst", "basis"), true);
  assert.equal(validWorkDetail({ ...detail, state: "disabled" }, "inst", "basis"), false);
  assert.equal(validConsumption(actual, "inst", "basis"), true);
  assert.equal(validConsumption({ ...actual, matches_norm: false }, "inst", "basis"), false);
  assert.equal(validConsumption({ ...actual, entries: [{ ...actual.entries[0], movement_id: "" }] }, "inst", "basis"), false);
  assert.equal(validConsumption(actual, "foreign", "basis"), false);
  assert.equal(validWorkDetail({ ...detail, consumption: actual, consumption_id: "different" }, "inst", "basis"), false);
});

test("billing context requires coherent removal metadata without changing consumption terms", () => {
  assert.equal(validWorkDetail({ ...detail, billing_state: "removed", invoice_removed_at: "2026-10-06T12:00:00Z" }, "inst", "basis"), true);
  assert.equal(validWorkDetail({ ...detail, billing_state: "removed" }, "inst", "basis"), false);
  assert.equal(validWorkDetail({ ...detail, invoice_removed_at: "2026-10-06T12:00:00Z" }, "inst", "basis"), false);
  assert.equal(validWorkDetail({ ...detail, billing_state: "guessed" }, "inst", "basis"), false);
  assert.equal(validWorkDetail({ ...detail, billing_state: "unknown", ticket_number: null }, "inst", "basis"), true);
});

test("removed invoice remains an explicit measured consumption with no automatic zero", async () => {
  sessionStorage.clear(); setAccessToken(token());
  const root = createRoot(document.getElementById("root")!), original = globalThis.fetch;
  const removed = { ...work, billing_state: "removed", invoice_removed_at: "2026-10-06T12:00:00Z" };
  let writes = 0;
  globalThis.fetch = async (url, options) => {
    if (options?.method === "POST") writes++;
    return response(String(url).includes("/consumption-work?") ? [removed] : String(url).includes("/items/") ? item : { ...detail, ...removed });
  };
  try {
    await act(async () => root.render(panel())); await open();
    assert.match(document.body.textContent!, /Retirée de la facture/);
    assert.match(document.body.textContent!, /ne détermine pas les quantités réellement utilisées/);
    assert.equal(document.querySelectorAll('input[inputmode="decimal"]').length, 0);
    assert.equal(document.querySelector<HTMLInputElement>('input[type="checkbox"]')!.checked, false);
    assert.equal(writes, 0);
  } finally { await act(async () => root.unmount()); globalThis.fetch = original; }
});

test("unauthorized contexts do not read; reception sees original norms without a write form and failed refresh hides them", async () => {
  sessionStorage.clear(); setAccessToken(token("staff", "collaboratrice"));
  const root = createRoot(document.getElementById("root")!), original = globalThis.fetch;
  let reads = 0, failed = false;
  globalThis.fetch = async url => { reads++; if (failed) throw new Error("Unavailable"); return response(String(url).includes("/consumption-work?") ? [work] : String(url).includes("/items/") ? item : detail); };
  try {
    await act(async () => root.render(panel())); assert.equal(reads, 0);
    setAccessToken(token("cashier", "accueil")); await act(async () => root.render(panel())); await open();
    assert.match(document.body.textContent!, /4,125 ml/); assert.equal(document.querySelectorAll("form").length, 0);
    failed = true; await act(async () => button("Actualiser la prestation").click());
    assert.doesNotMatch(document.body.textContent!, /4,125 ml/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = original; sessionStorage.clear(); }
});

test("saved consumption survives a lost POST, remains selectable after confirmation leaves pending work and verifies original before clearing", async () => {
  sessionStorage.clear(); setAccessToken(token()); sessionStorage.setItem(key, JSON.stringify(intent));
  let root = createRoot(document.getElementById("root")!);
  const original = globalThis.fetch; let posts = 0, originals = 0, stockReads = 0;
  globalThis.fetch = async (url, options) => {
    const path = String(url);
    if (options?.method === "POST") {
      assert.deepEqual(JSON.parse(String(options.body)), { entries: [{ item_id: "stock", quantity: "4.125" }], reason: actual.reason, idempotency_key: "original" });
      assert.ok(sessionStorage.getItem(key)); if (++posts === 1) throw new Error("Lost reply"); return response(actual);
    }
    if (path.endsWith("/consumptions/actual")) { originals++; return response(actual); }
    if (path.includes("/consumption-work?")) return response(posts ? [] : [work]);
    if (path.includes("/items/")) return response(item);
    return response(posts ? { ...detail, billing_state: "removed", invoice_removed_at: "2026-10-06T12:00:00Z", consumption_id: actual.id, consumption: actual } : detail);
  };
  try {
    await act(async () => root.render(panel(async () => { stockReads++; return true; }))); await open();
    await act(async () => button("Reprendre la consommation conserv\u00e9e").click());
    assert.ok(sessionStorage.getItem(key)); assert.equal(originals, 0);
    await act(async () => root.unmount()); root = createRoot(document.getElementById("root")!);
    await act(async () => root.render(panel(async () => { stockReads++; return true; })));
    await act(async () => button("Demande conserv\u00e9e : Care").click());
    await act(async () => button("Reprendre la consommation conserv\u00e9e").click());
    assert.equal(posts, 2); assert.equal(originals, 1); assert.equal(stockReads, 1); assert.equal(sessionStorage.getItem(key), null);
    assert.match(document.body.textContent!, /Consommation enregistr\u00e9e/);
    assert.match(document.body.textContent!, /4,125 ml/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = original; sessionStorage.clear(); }
});

test("failed fresh stock read and mismatched original quantities retain the original saved consumption", async () => {
  sessionStorage.clear(); setAccessToken(token()); sessionStorage.setItem(key, JSON.stringify(intent));
  const root = createRoot(document.getElementById("root")!), original = globalThis.fetch;
  let tampered = true, posts = 0;
  globalThis.fetch = async (url, options) => {
    if (options?.method === "POST") { posts++; return response(actual); }
    if (String(url).endsWith("/consumptions/actual")) return response(tampered ? { ...actual, entries: [{ ...actual.entries[0], quantity: "2.125" }], matches_norm: false } : actual);
    return response(String(url).includes("/consumption-work?") ? [work] : String(url).includes("/items/") ? item : detail);
  };
  try {
    await act(async () => root.render(panel(async () => false))); await open();
    await act(async () => button("Reprendre la consommation conserv\u00e9e").click()); assert.ok(sessionStorage.getItem(key));
    tampered = false; await act(async () => button("Reprendre la consommation conserv\u00e9e").click());
    assert.equal(posts, 2); assert.ok(sessionStorage.getItem(key)); assert.doesNotMatch(document.body.textContent!, /Consommation enregistr\u00e9e/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = original; sessionStorage.clear(); }
});

test("late prior-institute reads and writes cannot publish or clear an original request in the new scope", async () => {
  sessionStorage.clear(); setAccessToken(token()); sessionStorage.setItem(key, JSON.stringify(intent));
  const root = createRoot(document.getElementById("root")!), original = globalThis.fetch;
  let finish!: (value: Response) => void;
  globalThis.fetch = async (url, options) => options?.method === "POST" ? new Promise(resolve => { finish = resolve; }) : response(String(url).includes("/new/") ? [] : String(url).includes("/consumption-work?") ? [work] : String(url).includes("/items/") ? item : detail);
  try {
    await act(async () => root.render(panel())); await open();
    await act(async () => button("Reprendre la consommation conserv\u00e9e").click());
    setAccessToken(token("new-manager")); await act(async () => root.render(panel(async () => true, "new")));
    await act(async () => finish(response(actual)));
    assert.ok(sessionStorage.getItem(key)); assert.doesNotMatch(document.body.textContent!, /4,125|Actual measured quantity|Consommation enregistr\u00e9e/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = original; sessionStorage.clear(); }
});

test("measured inputs start empty and adopting planned quantities requires an explicit operator action", async () => {
  sessionStorage.clear(); setAccessToken(token());
  const root = createRoot(document.getElementById("root")!), original = globalThis.fetch;
  globalThis.fetch = async url => response(String(url).includes("/consumption-work?") ? [work] : String(url).includes("/items?") ? [item] : String(url).includes("/items/") ? item : detail);
  try {
    await act(async () => root.render(panel())); await open();
    assert.equal(document.querySelectorAll("input[inputmode='decimal']").length, 0);
    assert.equal(document.querySelector<HTMLInputElement>("input[type='checkbox']")!.checked, false);
    await act(async () => button("Utiliser les quantit\u00e9s pr\u00e9vues").click());
    assert.equal(document.querySelector<HTMLInputElement>("input[inputmode='decimal']")!.value, "4.125");
    assert.equal(sessionStorage.getItem(key), null);
  } finally { await act(async () => root.unmount()); globalThis.fetch = original; sessionStorage.clear(); }
});


test("late reads for a prior performed line cannot replace the newly selected original basis", async () => {
  sessionStorage.clear(); setAccessToken(token("cashier", "accueil"));
  const root = createRoot(document.getElementById("root")!), original = globalThis.fetch;
  const other = { ...work, basis_id: "other-basis", source_id: "other-source", service_id: "other", service_name: "Other", state: "unconfigured" };
  let finish!: (value: Response) => void, articleReads = 0;
  globalThis.fetch = async url => {
    if (String(url).includes("/consumption-work?")) return response([work, other]);
    if (String(url).endsWith("/bases/basis/work")) return new Promise(resolve => { finish = resolve; });
    if (String(url).includes("/items/")) { articleReads++; return response(item); }
    return response({ ...other, expected_entries: null, consumption: null });
  };
  try {
    await act(async () => root.render(panel())); await open();
    await act(async () => document.querySelectorAll<HTMLButtonElement>(".bm-stock-grid button")[1].click());
    await act(async () => finish(response(detail)));
    assert.equal(articleReads, 0); assert.doesNotMatch(document.body.textContent!, /4,125/);
    assert.match(document.body.textContent!, /Aucune norme configur\u00e9e/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = original; sessionStorage.clear(); }
});
