import test from "node:test";
import assert from "node:assert/strict";
import React, { act } from "react";
import { JSDOM } from "jsdom";
import { RevenueGuardianPanel } from "../src/components/RevenueGuardianPanel";
import { setAccessToken } from "../src/api/session";
import { validRevenueBilling, revenueAverage, revenueMoney } from "../src/revenue-utils";

// Contract fixture only; these tests do not claim native actual-backend acceptance.
const period = { start: "2026-10-04T22:00:00Z", end: "2026-10-05T22:00:00Z" };
const group = { currency: "CHF", source_count: 2, known_amount_count: 2, missing_amount_count: 0, invalid_amount_count: 0,
  known_gross_minor: "24691", complete_gross_minor: "24691", average_minor: { numerator: "24691", denominator: "2" } };
const report = { window: { institute_id: "inst", ...period, captured_at: "2026-10-06T12:00:00Z" },
  basis: "recorded_paid_tickets_and_active_invoice_lines", ticket_count: 2, ticket_amounts: [group], active_line_count: 2,
  service_mix: [{ service_id: "service", category: "care", currency: "CHF", line_count: 2, units: "2", amounts: group }],
  tickets_without_active_lines: 0, tickets_with_unknown_category: 0, care_tickets: 2, care_and_retail_tickets: 0,
  recorded_retail_attach_ratio: { numerator: "0", denominator: "2" }, institute_undated_paid_tickets: 3,
  complete_sales_history: false, settlement_confirmed: false, projected_revenue: null };
test("billing contract rejects inconsistent scope, clocks, source partitions, ratios and unsupported claims", () => {
  assert.equal(validRevenueBilling(report, "inst", period), true);
  const mutations = [
    { ...report, extra: 1 }, { ...report, complete_sales_history: 0 }, { ...report, settlement_confirmed: true },
    { ...report, projected_revenue: "0" }, { ...report, ticket_count: 3 },
    { ...report, window: { ...report.window, institute_id: "other" } },
    { ...report, window: { ...report.window, captured_at: period.start } },
    { ...report, recorded_retail_attach_ratio: { numerator: "1", denominator: "2" } },
    { ...report, ticket_amounts: [{ ...group, known_amount_count: 1 }] },
    { ...report, ticket_amounts: [{ ...group, known_gross_minor: "024691" }] },
    { ...report, ticket_amounts: [{ ...group, average_minor: { numerator: "24690", denominator: "2" } }] },
    { ...report, service_mix: [{ ...report.service_mix[0], units: "1" }] },
    { ...report, service_mix: [{ ...report.service_mix[0], currency: "EUR" }] },
  ];
  for (const value of mutations) assert.equal(validRevenueBilling(value, "inst", period), false);
  assert.equal(revenueMoney("9007199254740993"), "90071992547409.93");
  assert.equal(revenueAverage(group.average_minor), "≈ 123.46");
  assert.equal(revenueAverage({ numerator: "0", denominator: "2" }), "0.00");
});
const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (role = "responsable_institut") => `h.${Buffer.from(JSON.stringify({ sub: "manager", role })).toString("base64url")}.s`;
const reply = (v: unknown) => new Response(JSON.stringify(v), { headers: { "Content-Type": "application/json" } });
async function input(index: number, value: string) {
  await act(async () => {
    const el = document.querySelectorAll("input")[index];
    Object.getOwnPropertyDescriptor(dom.window.HTMLInputElement.prototype, "value")!.set!.call(el, value);
    el.dispatchEvent(new dom.window.Event("input", { bubbles: true }));
    el.dispatchEvent(new dom.window.Event("change", { bubbles: true }));
  });
}
async function click() { await act(async () => document.querySelector("button")!.click()); }
test("unknown currencies and incomplete recorded amounts remain unavailable rather than zero", async () => {
  const uncertain = { ...report, ticket_amounts: [
    { ...group, source_count: 1, known_amount_count: 0, missing_amount_count: 1, known_gross_minor: "0", complete_gross_minor: null, average_minor: null },
    { ...group, currency: null, source_count: 1, known_amount_count: 1, known_gross_minor: "12345", complete_gross_minor: null, average_minor: null },
  ], tickets_without_active_lines: 1, recorded_retail_attach_ratio: null };
  assert.equal(validRevenueBilling(uncertain, "inst", period), true);
  setAccessToken(token()); const root = createRoot(document.getElementById("root")!);
  globalThis.fetch = async () => reply(uncertain);
  try {
    await act(async () => root.render(<RevenueGuardianPanel institute="inst" timezone="Europe/Zurich" />));
    await input(0, "2026-10-05"); await input(1, "2026-10-06"); await click();
    assert.match(document.body.textContent!, /Sous-total connu, incomplet/);
    assert.match(document.body.textContent!, /Aucun montant connu/);
    assert.doesNotMatch(document.body.textContent!, /0\.00 CHF/);
    assert.match(document.body.textContent!, /Panier moyen : indisponible/);
    assert.match(document.body.textContent!, /Devise inconnue : montant monétaire non affiché/);
    assert.match(document.body.textContent!, /Association soin \/ produit : indisponible/);
    assert.doesNotMatch(document.body.textContent!, /123\.45/);
  } finally { await act(async () => root.unmount()); }
});
test("manager explicitly reads exact billing; malformed reread hides old money; role denies UI", async () => {
  setAccessToken(token()); const root = createRoot(document.getElementById("root")!);
  let calls = 0, corrupt = false;
  globalThis.fetch = async (url) => { calls++; assert.match(String(url), /revenue\/institutes\/inst\/billing\?/); return reply(corrupt ? { ...report, ticket_count: 3 } : report); };
  try {
    await act(async () => root.render(<RevenueGuardianPanel institute="inst" timezone="Europe/Zurich" />));
    assert.equal(calls, 0); await click(); assert.equal(calls, 0);
    await input(0, "2026-10-05"); await input(1, "2026-10-06"); await click();
    assert.equal(calls, 1); assert.match(document.body.textContent!, /246\.91 CHF/);
    assert.match(document.body.textContent!, /≈ 123\.46 CHF/);
    assert.match(document.body.textContent!, /3 tickets payés sans date/);
    corrupt = true; await click(); assert.ok(document.querySelector('[role="alert"]'));
    assert.doesNotMatch(document.body.textContent!, /246\.91 CHF/);
    setAccessToken(token("accueil")); await act(async () => root.render(<RevenueGuardianPanel institute="inst" timezone="Europe/Zurich" />));
    assert.equal(document.querySelector("button"), null);
  } finally { await act(async () => root.unmount()); }
});
test("edits, session replacement and institute replacement discard pending responses", async () => {
  setAccessToken(token()); const root = createRoot(document.getElementById("root")!);
  let resolve: (r: Response) => void = () => {};
  globalThis.fetch = () => new Promise<Response>(r => { resolve = r; });
  try {
    await act(async () => root.render(<RevenueGuardianPanel institute="inst" timezone="Europe/Zurich" />));
    await input(0, "2026-10-05"); await input(1, "2026-10-06"); await click();
    await input(0, "2026-10-04"); await act(async () => resolve(reply(report)));
    assert.doesNotMatch(document.body.textContent!, /246\.91 CHF/);
    await input(0, "2026-10-05"); await click(); setAccessToken(token("accueil"));
    await act(async () => resolve(reply(report))); assert.doesNotMatch(document.body.textContent!, /246\.91 CHF/);
    setAccessToken(token()); await click();
    await act(async () => root.render(<RevenueGuardianPanel institute="other" timezone="Europe/Zurich" />));
    await act(async () => resolve(reply(report))); assert.doesNotMatch(document.body.textContent!, /246\.91 CHF/);
  } finally { await act(async () => root.unmount()); }
});
