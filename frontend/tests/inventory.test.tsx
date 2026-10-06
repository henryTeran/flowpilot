import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import React, { act } from "react";
import { InventoryPanel } from "../src/components/InventoryPanel";
import { stockQuantity, validStockItem } from "../src/inventory-utils";
import { setAccessToken } from "../src/api/session";
const dom = new JSDOM("<!doctype html><div id='root'></div>", { url: "http://localhost:5173" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (sub = "manager", role = "responsable_institut") => `h.${Buffer.from(JSON.stringify({ sub, role })).toString("base64url")}.s`;
const response = (value: unknown) => new Response(JSON.stringify(value), { headers: { "Content-Type": "application/json" } });
const item = (institute_id = "inst") => ({ id: "stock", institute_id, sku: "SERUM", name: "Serum", category: "cabine", unit: "ml", reorder_threshold: "1.000", on_hand: "0.000", at_or_below_threshold: true, actor_id: "manager", created_at: "2026-10-06T10:00:00Z" });
const saved = { sku: "SERUM", name: "Serum", category: "cabine", unit: "ml", reorder_threshold: "1.000", reason: "Initial catalogue", idempotency_key: "original-key" };
const storage = `flowpilot.stock-request:${JSON.stringify(["inst", "manager", "create"])}`;
function button(text: string) { return Array.from(document.querySelectorAll<HTMLButtonElement>("button")).find(button => button.textContent === text)!; }

test("stock quantities stay exact, whole units and malformed snapshots are rejected", () => {
  assert.equal(stockQuantity("999999999999,999", "ml"), "999999999999.999");
  assert.equal(stockQuantity("-6", "ml", true), "-6.000");
  for (const value of ["1.0001", "NaN", "Infinity", "1000000000000", "1e3"]) assert.equal(stockQuantity(value, "ml"), undefined);
  assert.equal(stockQuantity("0.5", "unit"), undefined);
  assert.equal(validStockItem(item(), "foreign"), false);
  assert.equal(validStockItem({ ...item(), at_or_below_threshold: false }, "inst"), false);
  assert.equal(validStockItem({ ...item(), on_hand: "-1.000" }, "inst"), false);
  assert.equal(validStockItem({ ...item(), unit: "unit", on_hand: "1.500" }, "inst"), false);
});

test("empty and unauthorized stock contexts do not read; failed refresh hides cached facts", async () => {
  const root = createRoot(document.getElementById("root")!), original = globalThis.fetch;
  let reads = 0, failed = false;
  globalThis.fetch = async () => { reads++; if (failed) throw new Error("Unavailable"); return response([{ ...item(), on_hand: "999999999999.999", at_or_below_threshold: false }]); };
  try {
    setAccessToken(token("staff", "collaboratrice"));
    await act(async () => root.render(<InventoryPanel instituteId="inst" />));
    setAccessToken(token());
    await act(async () => root.render(<InventoryPanel instituteId="" />));
    assert.equal(reads, 0);
    await act(async () => root.render(<InventoryPanel instituteId="inst" />));
    assert.match(document.body.textContent!, /999999999999,999 ml/);
    failed = true;
    await act(async () => button("Actualiser le stock").click());
    assert.match(document.body.textContent!, /Unavailable/);
    assert.doesNotMatch(document.body.textContent!, /999999999999/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = original; sessionStorage.clear(); }
});

test("late institute and token reads cannot publish an old stock catalogue", async () => {
  const root = createRoot(document.getElementById("root")!), original = globalThis.fetch;
  let resolveOld!: (value: Response) => void;
  globalThis.fetch = async url => String(url).includes("/old/") ? new Promise(resolve => { resolveOld = resolve; }) : response([{ ...item("new"), name: "Current stock" }]);
  try {
    setAccessToken(token("old-manager"));
    await act(async () => root.render(<InventoryPanel instituteId="old" />));
    setAccessToken(token("new-manager"));
    await act(async () => root.render(<InventoryPanel instituteId="new" />));
    await act(async () => resolveOld(response([{ ...item("old"), name: "Old stock" }])));
    assert.match(document.body.textContent!, /Current stock/);
    assert.doesNotMatch(document.body.textContent!, /Old stock/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = original; sessionStorage.clear(); }
});

test("failed catalogue refresh also hides selected stock facts and disables movements", async () => {
  sessionStorage.clear(); setAccessToken(token());
  const root = createRoot(document.getElementById("root")!), original = globalThis.fetch;
  const row = { ...item(), on_hand: "34.125", at_or_below_threshold: false };
  let failed = false;
  globalThis.fetch = async url => {
    if (String(url).includes("/items?")) { if (failed) throw new Error("Catalogue unavailable"); return response([row]); }
    return response(String(url).includes("/movements") ? [] : row);
  };
  try {
    await act(async () => root.render(<InventoryPanel instituteId="inst" />));
    await act(async () => document.querySelector<HTMLButtonElement>(".bm-stock-card")!.click());
    assert.match(document.body.textContent!, /Stock enregistré : 34,125 ml/);
    failed = true;
    await act(async () => button("Actualiser le stock").click());
    assert.doesNotMatch(document.body.textContent!, /34,125|Historique des mouvements/);
    assert.equal(button("Enregistrer le mouvement").disabled, true);
  } finally { await act(async () => root.unmount()); globalThis.fetch = original; sessionStorage.clear(); }
});

test("lost creation and failed stock refresh retain the original request across remount", async () => {
  sessionStorage.clear(); setAccessToken(token()); sessionStorage.setItem(storage, JSON.stringify(saved));
  let root = createRoot(document.getElementById("root")!);
  const original = globalThis.fetch;
  let posts = 0, failRead = false;
  globalThis.fetch = async (url, options) => {
    if (options?.method === "POST") {
      assert.deepEqual(JSON.parse(String(options.body)), saved);
      assert.deepEqual(JSON.parse(sessionStorage.getItem(storage)!), saved);
      posts++;
      if (posts === 1) throw new Error("Lost response");
      if (posts === 2) failRead = true;
      return response(item());
    }
    if (failRead) throw new Error("Refresh unavailable");
    if (String(url).includes("/movements")) return response([]);
    return response(String(url).endsWith("/items/stock") ? item() : posts ? [item()] : []);
  };
  try {
    await act(async () => root.render(<InventoryPanel instituteId="inst" />));
    await act(async () => button("Reprendre la demande conservée").click());
    assert.ok(sessionStorage.getItem(storage)); assert.equal(posts, 1);
    await act(async () => root.unmount()); root = createRoot(document.getElementById("root")!);
    await act(async () => root.render(<InventoryPanel instituteId="inst" />));
    await act(async () => button("Reprendre la demande conservée").click());
    assert.equal(posts, 2); assert.ok(sessionStorage.getItem(storage));
    assert.doesNotMatch(document.body.textContent!, /Article enregistré\./);
    failRead = false;
    await act(async () => button("Actualiser le stock").click());
    await act(async () => button("Reprendre la demande conservée").click());
    assert.equal(posts, 3); assert.equal(sessionStorage.getItem(storage), null);
    assert.match(document.body.textContent!, /Article enregistré\./);
  } finally { await act(async () => root.unmount()); globalThis.fetch = original; sessionStorage.clear(); }
});

test("foreign write responses cannot release a saved stock request", async () => {
  sessionStorage.clear(); setAccessToken(token()); sessionStorage.setItem(storage, JSON.stringify(saved));
  const root = createRoot(document.getElementById("root")!), original = globalThis.fetch;
  let reads = 0;
  globalThis.fetch = async (_url, options) => { if (options?.method === "POST") return response(item("foreign")); reads++; return response([]); };
  try {
    await act(async () => root.render(<InventoryPanel instituteId="inst" />));
    await act(async () => button("Reprendre la demande conservée").click());
    assert.equal(reads, 1); assert.ok(sessionStorage.getItem(storage));
    assert.match(document.body.textContent!, /Résultat de la demande à vérifier/);
    assert.doesNotMatch(document.body.textContent!, /Article enregistré\./);
  } finally { await act(async () => root.unmount()); globalThis.fetch = original; sessionStorage.clear(); }
});

test("late stock writes cannot publish into a new signed institute context", async () => {
  sessionStorage.clear(); setAccessToken(token()); sessionStorage.setItem(storage, JSON.stringify(saved));
  const root = createRoot(document.getElementById("root")!), original = globalThis.fetch;
  let complete!: (value: Response) => void;
  globalThis.fetch = async (_url, options) => options?.method === "POST" ? new Promise(resolve => { complete = resolve; }) : response([]);
  try {
    await act(async () => root.render(<InventoryPanel instituteId="inst" />));
    await act(async () => button("Reprendre la demande conservée").click());
    setAccessToken(token("new-manager"));
    await act(async () => root.render(<InventoryPanel instituteId="new" />));
    await act(async () => complete(response(item())));
    assert.ok(sessionStorage.getItem(storage));
    assert.match(document.body.textContent!, /Aucun article enregistré/);
    assert.doesNotMatch(document.body.textContent!, /Article enregistré\.|Demande conservée|Serum/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = original; sessionStorage.clear(); }
});
