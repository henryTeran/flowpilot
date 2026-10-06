import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import React, { act } from "react";
import { instantMicros, validPlanned, validObserved } from "../src/source-outlook-utils";
import { StockSourceOutlook } from "../src/components/StockSourceOutlook";
import { setAccessToken } from "../src/api/session";
const dom = new JSDOM("<!doctype html><div id='root'></div>", { url: "http://localhost:5173" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const request = { starts_at: "2026-10-06T22:00:00Z", ends_at: "2026-10-07T22:00:00Z", include_waiting_queue: false };
const observedRequest = { starts_at: request.starts_at, ends_at: request.ends_at, observed_starts_at: "2026-10-05T22:00:00Z", observed_ends_at: "2026-10-06T22:00:00Z" };
const item = { item_id: "item", item_sku: "SERUM", item_name: "Serum", category: "cabine", unit: "ml", on_hand: "6.000", threshold: "4.125", at_or_below_threshold: false, threshold_shortfall: "0.000", pending_order_quantity: "8.000", known_demand: "4.125", complete_demand: "4.125", known_demand_shortfall: "2.250", conditional_shortfall_after_all_orders: "0.000" };
const planned = { ...request, institute_id: "inst", generated_at: "2026-10-07T10:00:00Z", effective_starts_at: "2026-10-07T10:00:00Z", limit: 20, offset: 0, source: "recorded_upcoming_demand", norm_basis: "provisional_current_at_read", queue_timing: "unscheduled_at_read", coverage: "complete_recorded_norms", appointment_count: 1, waiting_line_count: 0, service_quantity: 1, missing_norm_quantity: 0, disabled_norm_quantity: 0, items: [item] };
const { known_demand, complete_demand, known_demand_shortfall, ...physical } = item;
const observed = { ...planned, ...observedRequest, source: "signed_completed_service_usage", assumption: "constant_elapsed_time_pace", coverage: "complete_signed_sample", completed_executions: 1, captured_bases: 1, signed_confirmations: 1, pending_bases: 0, legacy_completed_executions: 0, undated_completed_executions: 0, items: [{ ...physical, observed_quantity: "4.125", recorded_pace_projection: "2.063", complete_pace_projection: "2.063", recorded_projection_shortfall: "0.188" }] };
test("source DTOs validate clipping, source counts, scope and exact projections", () => {
  assert.equal(validPlanned(planned, "inst", 0, request), true);
  for (const patch of [{ institute_id: "foreign" }, { effective_starts_at: request.starts_at }, { waiting_line_count: 1 }, { missing_norm_quantity: 1 }, { norm_basis: "captured_original" }, { items: [item, item] }]) assert.equal(validPlanned({ ...planned, ...patch }, "inst", 0, request), false);
  assert.equal(validObserved(observed, "inst", 0, observedRequest), true);
  for (const patch of [{ pending_bases: 1 }, { completed_executions: 0 }, { assumption: "learned_ai" }, { observed_ends_at: "2026-10-07T12:00:00Z" }, { items: [{ ...observed.items[0], recorded_pace_projection: "2.064", complete_pace_projection: "2.064", recorded_projection_shortfall: "0.189" }] }]) assert.equal(validObserved({ ...observed, ...patch }, "inst", 0, observedRequest), false);
  const partial = { ...observed, coverage: "partial_signed_sample", pending_bases: 1, captured_bases: 2, items: [{ ...observed.items[0], complete_pace_projection: null }] };
  assert.equal(validObserved(partial, "inst", 0, observedRequest), true);
  assert.equal(validObserved({ ...partial, items: [{ ...partial.items[0], complete_pace_projection: "0.000" }] }, "inst", 0, observedRequest), false);
});
test("microsecond pace and whole article rounding stay exact beyond safe Number quantities", () => {
  assert.equal(instantMicros("2026-10-07T10:00:00.123456Z")! - instantMicros("2026-10-07T10:00:00Z")!, 123456n);
  assert.equal(instantMicros("2026-02-30T00:00:00Z"), undefined);
  assert.equal(instantMicros("2026-10-07T10:00:00"), undefined);
  const huge = "99999999999999900000.000", milli = BigInt(huge.replace(".", "")), projected = (milli + 1n) / 2n;
  const q = (v: bigint) => `${v / 1000n}.${String(v % 1000n).padStart(3, "0")}`;
  const row = { ...observed.items[0], observed_quantity: huge, recorded_pace_projection: q(projected), complete_pace_projection: q(projected), recorded_projection_shortfall: q(projected - 1875n), conditional_shortfall_after_all_orders: q(projected - 9875n) };
  assert.equal(validObserved({ ...observed, completed_executions: 100000000, captured_bases: 100000000, signed_confirmations: 100000000, items: [row] }, "inst", 0, observedRequest), true);
  assert.equal(validObserved({ ...observed, items: [row] }, "inst", 0, observedRequest), false);
  const unit = { ...observed.items[0], unit: "unit", on_hand: "0.000", threshold: "0.000", pending_order_quantity: "0.000", at_or_below_threshold: true, observed_quantity: "1.000", recorded_pace_projection: "1.000", complete_pace_projection: "1.000", recorded_projection_shortfall: "1.000", conditional_shortfall_after_all_orders: "1.000" };
  assert.equal(validObserved({ ...observed, items: [unit] }, "inst", 0, observedRequest), true);
});
test("source response arithmetic retains sub-millisecond future and observation durations", () => {
  const smallRequest = { starts_at: "2026-10-07T10:00:00.123456Z", ends_at: "2026-10-07T10:00:00.123459Z", observed_starts_at: "2026-10-07T10:00:00.123449Z", observed_ends_at: "2026-10-07T10:00:00.123456Z" };
  const small = { ...observed, ...smallRequest, generated_at: smallRequest.starts_at, effective_starts_at: smallRequest.starts_at, items: [{ ...observed.items[0], observed_quantity: "0.007", recorded_pace_projection: "0.003", complete_pace_projection: "0.003", recorded_projection_shortfall: "0.000" }] };
  assert.equal(validObserved(small, "inst", 0, smallRequest), true);
  assert.equal(validObserved({ ...small, items: [{ ...small.items[0], recorded_pace_projection: "0.000", complete_pace_projection: "0.000" }] }, "inst", 0, smallRequest), false);
});
const token = (role = "responsable_institut", sub = "manager") => `h.${Buffer.from(JSON.stringify({ role, sub })).toString("base64url")}.s`;
const reply = (value: unknown) => new Response(JSON.stringify(value), { headers: { "Content-Type": "application/json" } });
const panel = (usable = true, institute = "inst") => <StockSourceOutlook institute={institute} timezone="Europe/Zurich" usable={usable} />;
async function fill(index: number, value: string) {
  await act(async () => { const input = document.querySelectorAll<HTMLInputElement>('input[type="date"]')[index]; Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value")!.set!.call(input, value); input.dispatchEvent(new window.Event("input", { bubbles: true })); input.dispatchEvent(new window.Event("change", { bubbles: true })); });
}
async function submit() { await act(async () => document.querySelector("form")!.dispatchEvent(new window.Event("submit", { bubbles: true, cancelable: true }))); }
test("source view is on demand, hides invalidated facts and refuses a malformed refresh", async () => {
  sessionStorage.clear(); setAccessToken(token()); const root = createRoot(document.getElementById("root")!), previous = globalThis.fetch;
  let reads = 0, invalid = false; globalThis.fetch = async () => { reads++; return reply(invalid ? { ...planned, institute_id: "foreign" } : planned); };
  try {
    await act(async () => root.render(panel())); assert.equal(reads, 0);
    await fill(0, "2026-10-07"); await fill(1, "2026-10-08"); await submit();
    assert.equal(reads, 1); assert.match(document.body.textContent!, /Stock physique : 6,000 ml/);
    await act(async () => root.render(panel(false))); assert.doesNotMatch(document.body.textContent!, /Stock physique :/);
    invalid = true; await act(async () => root.render(panel())); assert.ok(document.querySelector('[role="alert"]')); assert.doesNotMatch(document.body.textContent!, /Stock physique :/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = previous; }
});
test("staff reads nothing and old scope results cannot revive facts after remount", async () => {
  sessionStorage.clear(); setAccessToken(token("collaboratrice")); const root = createRoot(document.getElementById("root")!), previous = globalThis.fetch;
  let reads = 0, finish!: (r: Response) => void; globalThis.fetch = async () => { reads++; return new Promise(resolve => { finish = resolve; }); };
  try {
    await act(async () => root.render(panel())); assert.equal(reads, 0);
    setAccessToken(token()); await act(async () => root.render(panel())); await fill(0, "2026-10-07"); await fill(1, "2026-10-08"); await submit(); assert.equal(reads, 1);
    setAccessToken(token("responsable_institut", "other")); await act(async () => root.render(panel(true, "other"))); await act(async () => finish(reply(planned)));
    assert.doesNotMatch(document.body.textContent!, /Stock physique :|Serum/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = previous; }
});
