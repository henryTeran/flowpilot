import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import React, { act } from "react";
import { EmployeeCommissionPanel, commissionAmount } from "../src/components/EmployeeCommissionPanel";
import { setAccessToken } from "../src/api/session";
import { props, snapshot } from "./commission-fixture";
import { commissionStates, type CommissionDay } from "../src/commission-utils";
const dom = new JSDOM("<!doctype html><div id='root'></div>", { url: "http://localhost:5173" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (role = "responsable_institut", actor = "manager") => `h.${Buffer.from(JSON.stringify({ role, sub: actor })).toString("base64url")}.s`;
const reply = (employee = "emp") => { const r = snapshot(); r.employee_id = employee; const o = r.rows[0].original;
  o.employee_id = o.rule_capture.employee_id = o.calculation.terms.employee_id = o.calculation.source.employee_id = employee;
  return new Response(JSON.stringify(r), { headers: { "Content-Type": "application/json" } }); };
test("commission profile isolates employee/actor replies and refuses incoherent fresh totals", async () => {
  const fetch = globalThis.fetch, root = createRoot(document.getElementById("root")!), pending: ((v: Response) => void)[] = [];
  globalThis.fetch = async () => new Promise(resolve => pending.push(resolve));
  try {
    setAccessToken(token("accueil")); await act(async () => root.render(<EmployeeCommissionPanel {...props} />)); assert.equal(pending.length, 0);
    setAccessToken(token()); await act(async () => root.render(<EmployeeCommissionPanel {...props} />));
    await act(async () => root.render(<EmployeeCommissionPanel {...props} employee="other" />));
    await act(async () => pending[0](reply())); assert.equal(document.querySelectorAll("li").length, 0);
    setAccessToken(token("responsable_institut", "new")); await act(async () => root.render(<EmployeeCommissionPanel {...props} employee="other" />));
    await act(async () => pending[1](reply("other"))); assert.equal(document.querySelectorAll("li").length, 0);
    await act(async () => pending[2](reply("other"))); assert.match(document.body.textContent!, /1,04 CHF/); assert.match(document.body.textContent!, /UTC\+01:00/);
    assert.match(document.body.textContent!, /total à payer restent inconnus/); assert.match(document.body.textContent!, /quantité : 3, déjà incluse/);
    await act(async () => document.querySelector<HTMLButtonElement>("button")!.click()); assert.equal(document.querySelectorAll("li").length, 0);
    const forged = await reply("other").json(); forged.currencies[0].amounts_minor.recorded = "105";
    await act(async () => pending[3](new Response(JSON.stringify(forged), { headers: { "Content-Type": "application/json" } })));
    assert.match(document.body.textContent!, /à vérifier/); assert.equal(document.querySelectorAll("li").length, 0);
  } finally { await act(async () => root.unmount()); globalThis.fetch = fetch; }
});
test("commission money display preserves cents beyond safe Number precision without currency conversion", () => {
  assert.equal(commissionAmount("9007199254740993", "CHF"), "90071992547409,93 CHF");
  assert.equal(commissionAmount("0", "EUR"), "0,00 EUR"); assert.equal(commissionAmount("104", "CHF"), "1,04 CHF");
});
test("profile presents recorded, cancelled and future-clock money separately for each currency", async () => {
  const fetch = globalThis.fetch, root = createRoot(document.getElementById("root")!); const r = snapshot();
  r.rows = commissionStates.map((state, index) => { const o = snapshot().rows[0].original;
    o.id = `commission-${index}`; o.line_id = o.calculation.source.line_id = `line-${index}`;
    if (state === "future_recording") o.created_at = o.calculation.source.captured_at = "2026-10-25T12:00:00.000003Z";
    if (state === "cancelled" || state === "future_cancellation") o.cancellation = { id: `cancel-${index}`, institute_id: "inst", commission_id: o.id,
      actor_id: "manager", reason: "Correction", idempotency_key: `cancel-key-${index}`, created_at: state === "cancelled" ? r.generated_at : "2026-10-25T12:00:00.000003Z" };
    if (state === "cancelled") { o.rule_id = o.rule_capture.id = "rule-eur"; o.rule_capture.currency = o.calculation.terms.currency = o.calculation.source.currency = "EUR"; }
    return { original: o, state };
  });
  r.page.total = 4; r.counts = Object.fromEntries(commissionStates.map(k => [k, 1])) as CommissionDay["counts"];
  r.currencies = (["CHF", "EUR"] as const).map(currency => ({ currency,
    counts: Object.fromEntries(commissionStates.map(k => [k, (k === "cancelled") === (currency === "EUR") ? 1 : 0])) as CommissionDay["counts"],
    amounts_minor: Object.fromEntries(commissionStates.map(k => [k, (k === "cancelled") === (currency === "EUR") ? "104" : "0"])) as CommissionDay["currencies"][number]["amounts_minor"] }));
  globalThis.fetch = async () => new Response(JSON.stringify(r), { headers: { "Content-Type": "application/json" } });
  try {
    setAccessToken(token()); await act(async () => root.render(<EmployeeCommissionPanel {...props} />));
    assert.equal(document.querySelectorAll("li").length, 4); assert.equal(document.querySelectorAll("[aria-label^='Montants enregistrés en']").length, 2);
    assert.match(document.body.textContent!, /Commissions annulées : 1,04 EUR/); assert.match(document.body.textContent!, /Enregistrements datés après la lecture : 1,04 CHF/);
    assert.match(document.body.textContent!, /Annulations datées après la lecture : 1,04 CHF/); assert.equal(document.querySelectorAll("input, select").length, 0);
  } finally { await act(async () => root.unmount()); globalThis.fetch = fetch; }
});
test("bounded profile pages retain global amounts and reset when the selected day changes", async () => {
  const fetch = globalThis.fetch, root = createRoot(document.getElementById("root")!); const paths: string[] = [];
  globalThis.fetch = async url => {
    const path = String(url); paths.push(path); const offset = path.includes("offset=20") ? 20 : 0, r = snapshot();
    r.page = { offset, limit: 20, total: 21 }; r.counts.recorded = r.currencies[0].counts.recorded = 21; r.currencies[0].amounts_minor.recorded = "2184";
    r.rows = Array.from({ length: offset ? 1 : 20 }, (_, index) => { const row = snapshot().rows[0]; row.original.id = `commission-${offset+index}`;
      row.original.line_id = row.original.calculation.source.line_id = `line-${offset+index}`; return row; });
    return new Response(JSON.stringify(r), { headers: { "Content-Type": "application/json" } });
  };
  const button = (label: string) => [...document.querySelectorAll<HTMLButtonElement>("button")].find(b => b.textContent === label)!;
  try {
    setAccessToken(token()); await act(async () => root.render(<EmployeeCommissionPanel {...props} />)); assert.equal(document.querySelectorAll("li").length, 20);
    await act(async () => button("Commissions suivantes").click()); assert.equal(document.querySelectorAll("li").length, 1); assert.match(document.body.textContent!, /21,84 CHF/);
    assert.equal(button("Commissions suivantes").disabled, true); assert.equal(button("Commissions précédentes").disabled, false);
    await act(async () => root.render(<EmployeeCommissionPanel {...props} day="2026-10-26" />));
    assert.ok(paths.at(-1)!.endsWith("limit=20&offset=0")); assert.equal(document.querySelectorAll("li").length, 0); assert.match(document.body.textContent!, /à vérifier/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = fetch; }
});
