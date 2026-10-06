import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import React, { act } from "react";
import { instituteMidnight, validOutlook, validScenario } from "../src/outlook-utils";
import { StockOutlook } from "../src/components/StockOutlook";
import { setAccessToken } from "../src/api/session";
const dom = new JSDOM("<!doctype html><div id='root'></div>", { url: "http://localhost:5173" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (sub = "manager", role = "responsable_institut") => `h.${Buffer.from(JSON.stringify({ sub, role })).toString("base64url")}.s`;
const response = (data: unknown) => new Response(JSON.stringify(data), { headers: { "Content-Type": "application/json" } });
const row = { item_id: "item", item_name: "Serum", item_sku: "SERUM", category: "cabine", unit: "ml", on_hand: "2.125", threshold: "4.125", at_or_below_threshold: true, threshold_shortfall: "2.000", pending_order_quantity: "8.000", known_demand: "0.000", complete_demand: null, known_demand_shortfall: "2.000", conditional_shortfall_after_all_orders: "0.000" };
const facts = { institute_id: "inst", generated_at: "2026-10-07T00:00:00Z", starts_at: null, ends_at: null, source: "recorded_stock", coverage: "not_applicable", demands: [], limit: 20, offset: 0, items: [row] };
const scenario = { starts_at: "2026-10-07T07:00:00Z", ends_at: "2026-10-14T07:00:00Z", demands: [{ service_id: "svc", quantity: 3, recipe_id: "recipe" }] };
const panel = (institute = "inst", usable = true) => <StockOutlook institute={institute} timezone="Europe/Zurich" services={[]} usable={usable} />;
function button(name: string) { return [...document.querySelectorAll<HTMLButtonElement>("button")].find(row => row.textContent === name)!; }

test("institute date boundaries resolve DST and reject invalid or skipped civil dates", () => {
  assert.equal(instituteMidnight("2026-10-07", "Europe/Zurich"), "2026-10-06T22:00:00.000Z");
  assert.equal(instituteMidnight("2026-03-29", "Europe/Zurich"), "2026-03-28T23:00:00.000Z");
  assert.equal(instituteMidnight("2026-03-30", "Europe/Zurich"), "2026-03-29T22:00:00.000Z");
  assert.equal(instituteMidnight("2026-10-07", "Asia/Kathmandu"), "2026-10-06T18:15:00.000Z");
  for (const [date, zone] of [["2026-02-30", "UTC"], ["2011-12-30", "Pacific/Apia"], ["2026-11-01", "America/Havana"], ["2026-10-07", "invalid"], ["2026-1-1", "UTC"]]) assert.equal(instituteMidnight(date, zone), undefined);
  assert.equal(validScenario(scenario), true); assert.equal(validScenario({ ...scenario, demands: [{ ...scenario.demands[0], quantity: true }] }), false);
});

test("outlook validates scope, page, exact arithmetic, units and incomplete coverage", () => {
  assert.equal(validOutlook(facts, "inst", 0), true);
  for (const changed of [{ ...facts, institute_id: "foreign" }, { ...facts, offset: 20 }, { ...facts, items: [null] }, { ...facts, items: [row, row] }, { ...facts, items: [{ ...row, known_demand_shortfall: "1.000" }] }, { ...facts, items: [{ ...row, on_hand: "2.125", unit: "unit" }] }]) assert.equal(validOutlook(changed, "inst", 0), false);
  const large = { ...facts, ...scenario, source: "explicit_service_volume_scenario", coverage: "complete_selected_norms", demands: [{ ...scenario.demands[0], service_name: "Prestation", recipe_revision: 1, state: "enabled" }], items: [{ ...row, known_demand: "99999999999999900.000", complete_demand: "99999999999999900.000", known_demand_shortfall: "99999999999999902.000", conditional_shortfall_after_all_orders: "99999999999999894.000" }] };
  assert.equal(validOutlook(large, "inst", 0, scenario), true);
  const missing = { ...scenario, demands: [{ ...scenario.demands[0], recipe_id: null }] };
  const partial = { ...large, coverage: "partial_selected_norms", demands: [{ ...missing.demands[0], service_name: "Prestation", recipe_revision: null, state: "missing_selected_norm" }], items: [{ ...row, complete_demand: null }] };
  assert.equal(validOutlook(partial, "inst", 0, missing), true);
  assert.equal(validOutlook({ ...partial, items: [{ ...row, complete_demand: "0.000" }] }, "inst", 0, missing), false);
});

test("reception reads physical shortages separately from orders and hides failed refresh", async () => {
  sessionStorage.clear(); setAccessToken(token("reader", "accueil")); const root = createRoot(document.getElementById("root")!), previous = globalThis.fetch;
  let invalid = false; globalThis.fetch = async () => response(invalid ? { ...facts, items: [{ ...row, threshold_shortfall: "0.000" }] } : facts);
  try {
    await act(async () => root.render(panel())); assert.match(document.body.textContent!, /Stock physique : 2,125 ml/); assert.match(document.body.textContent!, /Commandé, non reçu : 8,000 ml/); assert.equal(document.querySelectorAll("form").length, 1);
    invalid = true; await act(async () => button("Actualiser les besoins").click()); assert.doesNotMatch(document.body.textContent!, /Stock physique :/); assert.ok(document.querySelector('[role="alert"]'));
  } finally { await act(async () => root.unmount()); globalThis.fetch = previous; }
});

test("staff requests nothing and parent stock invalidation removes cached forecast facts", async () => {
  sessionStorage.clear(); setAccessToken(token("staff", "collaboratrice")); const root = createRoot(document.getElementById("root")!), previous = globalThis.fetch;
  let reads = 0; globalThis.fetch = async () => { reads++; return response(facts); };
  try {
    await act(async () => root.render(panel())); assert.equal(reads, 0); setAccessToken(token()); await act(async () => root.render(panel())); assert.match(document.body.textContent!, /Stock physique :/);
    await act(async () => root.render(panel("inst", false))); assert.doesNotMatch(document.body.textContent!, /Stock physique :/);
    await act(async () => root.render(panel())); assert.match(document.body.textContent!, /Stock physique :/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = previous; }
});

test("late old institute read cannot publish into a different signed session", async () => {
  sessionStorage.clear(); setAccessToken(token()); const root = createRoot(document.getElementById("root")!), previous = globalThis.fetch;
  let finish!: (response: Response) => void; globalThis.fetch = async url => String(url).includes("/inst/") ? new Promise(resolve => { finish = resolve; }) : response({ ...facts, institute_id: "other", items: [] });
  try {
    await act(async () => root.render(panel())); setAccessToken(token("other")); await act(async () => root.render(panel("other"))); await act(async () => finish(response(facts))); assert.doesNotMatch(document.body.textContent!, /Serum|Stock physique :/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = previous; }
});

test("stock invalidation and a failed fresh read cannot revive an older valid outlook", async () => {
  sessionStorage.clear(); setAccessToken(token()); const root = createRoot(document.getElementById("root")!), previous = globalThis.fetch;
  let finish!: (response: Response) => void, reads = 0;
  globalThis.fetch = async () => ++reads === 1 ? new Promise(resolve => { finish = resolve; }) : response({ ...facts, institute_id: "foreign" });
  try {
    await act(async () => root.render(panel())); await act(async () => root.render(panel("inst", false))); await act(async () => root.render(panel())); assert.ok(document.querySelector('[role="alert"]'));
    await act(async () => finish(response(facts))); assert.doesNotMatch(document.body.textContent!, /Stock physique :|Serum/); assert.ok(document.querySelector('[role="alert"]'));
  } finally { await act(async () => root.unmount()); globalThis.fetch = previous; }
});
