import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import React, { act } from "react";
import { StockOrders } from "../src/components/StockOrders";
import { usePurchaseWrite, type PurchaseSaved } from "../src/components/purchase-write";
import { validOrder, validReceipt, validProgress, type Order, type Receipt } from "../src/order-utils";
import { setAccessToken } from "../src/api/session";
const dom = new JSDOM("<!doctype html><div id='root'></div>", { url: "http://localhost:5173" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (sub = "manager", role = "responsable_institut") => `h.${Buffer.from(JSON.stringify({ sub, role })).toString("base64url")}.s`;
const response = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { "Content-Type": "application/json" } });
const entries = [{ item_id: "item", item_name: "Serum", item_sku: "SERUM", unit: "ml" as const, quantity: "10.125" }];
const order: Order = { id: "order", institute_id: "inst", supplier_id: "supplier", supplier_name: "Supplier", supplier_reference: "SUP", reference: "PO-1", reason: "Approved purchase", actor_id: "manager", idempotency_key: "order-key", created_at: "2026-10-07T10:00:00Z", entries };
const receipt: Receipt = { id: "receipt", institute_id: "inst", order_id: "order", reason: "Measured delivery", actor_id: "manager", idempotency_key: "receipt-key", occurred_at: "2026-10-07T10:01:00Z", entries: [{ item_id: "item", unit: "ml", quantity: "2.125", movement_id: "movement" }] };
const progress = (received = "2.125", remaining = "8.000", state = "partial") => ({ institute_id: "inst", order_id: "order", state, entries: [{ ...entries[0], received, remaining }] });
const savedOrder: PurchaseSaved = { payload: { supplier_id: order.supplier_id, reference: order.reference, reason: order.reason, idempotency_key: order.idempotency_key, entries: entries.map(({ item_name, item_sku, ...row }) => row) }, label: order.reference, entries, supplier_name: order.supplier_name, supplier_reference: order.supplier_reference };
const savedReceipt: PurchaseSaved = { payload: { reason: receipt.reason, idempotency_key: receipt.idempotency_key, entries: receipt.entries.map(({ movement_id, ...row }) => row) }, label: order.reference, entries: [{ ...entries[0], quantity: "2.125" }], order };
const key = (kind = "order") => `flowpilot.purchase-request:${JSON.stringify(["inst", "manager", kind, kind === "order" ? "create" : "order"])}`;
function button(name: string) { return [...document.querySelectorAll<HTMLButtonElement>("button")].find(row => row.textContent === name)!; }
function Harness({ kind = "order", refresh = async () => true, invalidate = () => {} }: { kind?: "order" | "receipt"; refresh?: (original: Order | Receipt) => Promise<boolean>; invalidate?: () => void }) {
  const write = usePurchaseWrite("inst", kind, kind === "receipt" ? order : undefined, true, refresh, invalidate);
  return <><button disabled={write.blocked} onClick={() => void write.run(write.saved || (kind === "order" ? savedOrder : savedReceipt))}>Run</button>{write.rejected && <button onClick={write.correct}>Correct</button>}<p>{write.error}</p><p>{write.success}</p></>;
}

test("purchase snapshots reject malformed, foreign, inconsistent and changed original quantities", () => {
  assert.equal(validOrder(order, "inst"), true); assert.equal(validReceipt(receipt, order), true); assert.equal(validProgress(progress(), order), true);
  for (const value of [null, { ...progress(), entries: [null] }, progress("2.125", "8.001"), progress("2.125", "8.000", "received"), { ...progress(), institute_id: "foreign" }, { ...progress(), entries: [{ ...entries[0], item_name: "Changed", received: "2.125", remaining: "8.000" }] }]) assert.equal(validProgress(value, order), false);
  assert.equal(validReceipt({ ...receipt, entries: [{ ...receipt.entries[0], quantity: "11.000" }] }, order), false);
  assert.equal(validOrder({ ...order, created_at: "2026-10-07T10:00:00" }, "inst"), false);
  assert.equal(validOrder({ ...order, entries: [{ ...entries[0], unit: "unit" }] }, "inst"), false);
});

test("lost order reply survives remount, original read error and failed refresh without correction", async () => {
  sessionStorage.clear(); setAccessToken(token()); sessionStorage.setItem(key(), JSON.stringify(savedOrder));
  let root = createRoot(document.getElementById("root")!), posts = 0, originalFailure = true, fresh = false;
  const previous = globalThis.fetch;
  globalThis.fetch = async (_url, options) => { if (options?.method === "POST") { posts++; assert.deepEqual(JSON.parse(String(options.body)), savedOrder.payload); if (posts === 1) throw new Error("Lost reply"); return response(order); } return originalFailure ? response({ detail: "Original unavailable" }, 400) : response(order); };
  try {
    await act(async () => root.render(<Harness refresh={async () => fresh} />)); await act(async () => button("Run").click()); assert.ok(sessionStorage.getItem(key()));
    await act(async () => root.unmount()); root = createRoot(document.getElementById("root")!); await act(async () => root.render(<Harness refresh={async () => fresh} />));
    await act(async () => button("Run").click()); assert.ok(sessionStorage.getItem(key())); assert.equal(button("Correct"), undefined);
    originalFailure = false; await act(async () => button("Run").click()); assert.ok(sessionStorage.getItem(key()));
    fresh = true; await act(async () => button("Run").click()); assert.equal(posts, 4); assert.equal(sessionStorage.getItem(key()), null);
  } finally { await act(async () => root.unmount()); globalThis.fetch = previous; }
});

test("receipt replay invalidates before POST and requires its exact original movement and actor", async () => {
  sessionStorage.clear(); setAccessToken(token()); sessionStorage.setItem(key("receipt"), JSON.stringify(savedReceipt));
  const root = createRoot(document.getElementById("root")!), previous = globalThis.fetch;
  let invalidated = 0, refreshed = 0, wrong = true;
  globalThis.fetch = async (_url, options) => { if (options?.method === "POST") { assert.ok(invalidated > 0); assert.deepEqual(JSON.parse(String(options.body)), savedReceipt.payload); return response(receipt); } return response(wrong ? { ...receipt, actor_id: "other" } : receipt); };
  try {
    await act(async () => root.render(<Harness kind="receipt" invalidate={() => invalidated++} refresh={async original => { assert.deepEqual(original, receipt); refreshed++; return true; }} />));
    await act(async () => button("Run").click()); assert.ok(sessionStorage.getItem(key("receipt"))); assert.equal(refreshed, 0);
    wrong = false; await act(async () => button("Run").click()); assert.equal(refreshed, 1); assert.equal(sessionStorage.getItem(key("receipt")), null);
  } finally { await act(async () => root.unmount()); globalThis.fetch = previous; }
});

test("late old-session purchase write preserves recovery and cannot refresh", async () => {
  sessionStorage.clear(); setAccessToken(token()); const root = createRoot(document.getElementById("root")!), previous = globalThis.fetch;
  let finish!: (value: Response) => void, refreshed = 0;
  globalThis.fetch = async () => new Promise(resolve => { finish = resolve; });
  try {
    await act(async () => root.render(<Harness refresh={async () => { refreshed++; return true; }} />)); await act(async () => button("Run").click());
    setAccessToken(token("other")); await act(async () => finish(response(order))); assert.ok(sessionStorage.getItem(key())); assert.equal(refreshed, 0);
  } finally { await act(async () => root.unmount()); globalThis.fetch = previous; }
});

test("corrupted saved purchase blocks a replacement, while definitive POST rejection permits correction", async () => {
  sessionStorage.clear(); setAccessToken(token()); sessionStorage.setItem(key(), "broken"); let root = createRoot(document.getElementById("root")!);
  const previous = globalThis.fetch; let posts = 0; globalThis.fetch = async () => { posts++; return response({ detail: "Duplicate reference" }, 400); };
  try {
    await act(async () => root.render(<Harness />)); assert.equal(button("Run").disabled, true); assert.equal(sessionStorage.getItem(key()), "broken"); assert.equal(posts, 0);
    await act(async () => root.unmount()); sessionStorage.setItem(key(), JSON.stringify(savedOrder)); root = createRoot(document.getElementById("root")!);
    await act(async () => root.render(<Harness />)); await act(async () => button("Run").click()); assert.ok(sessionStorage.getItem(key()));
    setAccessToken(token("other")); await act(async () => button("Correct").click()); assert.ok(sessionStorage.getItem(key()));
    setAccessToken(token()); await act(async () => button("Correct").click()); assert.equal(sessionStorage.getItem(key()), null);
  } finally { await act(async () => root.unmount()); globalThis.fetch = previous; }
});

test("orders are readonly for reception, hide failed facts and make no request for staff", async () => {
  sessionStorage.clear(); setAccessToken(token("staff", "collaboratrice")); const root = createRoot(document.getElementById("root")!), previous = globalThis.fetch;
  let reads = 0, foreign = false;
  globalThis.fetch = async url => { reads++; const path = String(url); return response(path.includes("/progress") ? progress() : path.includes("/receipts?") ? [receipt] : path.endsWith("/order") ? order : [{ ...order, institute_id: foreign ? "foreign" : "inst" }]); };
  const panel = <StockOrders institute="inst" onStockRefresh={async () => true} onStockInvalidate={() => {}} />;
  try {
    await act(async () => root.render(panel)); assert.equal(reads, 0); setAccessToken(token("cashier", "accueil")); await act(async () => root.render(<StockOrders institute="inst" onStockRefresh={async () => true} onStockInvalidate={() => {}} />));
    await act(async () => document.querySelector<HTMLButtonElement>(".bm-stock-card")!.click()); assert.match(document.body.textContent!, /Réception partielle/); assert.match(document.body.textContent!, /Dates : UTC/); assert.ok(document.body.textContent!.includes(new Date(receipt.occurred_at).toLocaleString("fr-CH", { timeZone: "UTC" }))); assert.equal(document.querySelectorAll("form").length, 0);
    foreign = true; await act(async () => button("Actualiser les commandes").click()); assert.doesNotMatch(document.body.textContent!, /Réception partielle|Reste à recevoir/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = previous; }
});

test("storage write failure or changed signed session prevents any new purchase POST", async () => {
  sessionStorage.clear(); setAccessToken(token()); const root = createRoot(document.getElementById("root")!), previous = globalThis.fetch, originalStore = dom.window.Storage.prototype.setItem;
  let posts = 0; globalThis.fetch = async () => { posts++; return response(order); };
  try {
    await act(async () => root.render(<Harness />));
    dom.window.Storage.prototype.setItem = () => { throw new Error("Storage unavailable"); };
    await act(async () => button("Run").click()); assert.equal(posts, 0); assert.match(document.body.textContent!, /Storage unavailable/);
    dom.window.Storage.prototype.setItem = originalStore;
    setAccessToken(token("other")); await act(async () => button("Run").click()); assert.equal(posts, 0); assert.equal(sessionStorage.getItem(key()), null);
  } finally { dom.window.Storage.prototype.setItem = originalStore; await act(async () => root.unmount()); globalThis.fetch = previous; }
});

test("saved receipt outside order page is selectable and remains replayable when fully received", async () => {
  sessionStorage.clear(); setAccessToken(token()); sessionStorage.setItem(key("receipt"), JSON.stringify(savedReceipt));
  const root = createRoot(document.getElementById("root")!), previous = globalThis.fetch; let posts = 0;
  globalThis.fetch = async (url, options) => { const path = String(url); if (options?.method === "POST") { posts++; return response(receipt); } return response(path.includes("/purchase-receipts/") ? receipt : path.includes("/progress") ? progress("10.125", "0.000", "received") : path.includes("/receipts?") ? [receipt] : path.endsWith("/order") ? order : []); };
  try {
    await act(async () => root.render(<StockOrders institute="inst" onStockRefresh={async () => true} onStockInvalidate={() => {}} />)); await act(async () => button("Reprendre la réception de PO-1").click());
    assert.match(document.body.textContent!, /Entièrement reçue/); const form = document.querySelector<HTMLFormElement>('form[aria-label="Recevoir une livraison"]')!; assert.equal(form.querySelector("fieldset")!.disabled, true); assert.equal(button("Reprendre la demande originale").disabled, false);
    await act(async () => button("Reprendre la demande originale").click()); assert.equal(posts, 1); assert.equal(sessionStorage.getItem(key("receipt")), null); assert.equal(button("Reprendre la réception de PO-1"), undefined);
  } finally { await act(async () => root.unmount()); globalThis.fetch = previous; }
});

test("fresh progress that omits the original receipt cannot release its saved request", async () => {
  sessionStorage.clear(); setAccessToken(token()); sessionStorage.setItem(key("receipt"), JSON.stringify(savedReceipt));
  const root = createRoot(document.getElementById("root")!), previous = globalThis.fetch; let posted = false, stocks = 0;
  globalThis.fetch = async (url, options) => { const path = String(url); if (options?.method === "POST") { posted = true; return response(receipt); } return response(path.includes("/purchase-receipts/") ? receipt : path.includes("/progress") ? (posted ? progress("0.000", "10.125", "pending") : progress()) : path.includes("/receipts?") ? [] : path.endsWith("/order") ? order : path.includes("/orders?") ? [order] : []); };
  try {
    await act(async () => root.render(<StockOrders institute="inst" onStockRefresh={async () => { stocks++; return true; }} onStockInvalidate={() => {}} />)); await act(async () => button("Reprendre la réception de PO-1").click());
    await act(async () => button("Reprendre la demande originale").click()); assert.ok(sessionStorage.getItem(key("receipt"))); assert.equal(stocks, 0); assert.match(document.body.textContent!, /Réception originale absente/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = previous; }
});
