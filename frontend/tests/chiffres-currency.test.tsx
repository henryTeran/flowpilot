import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import React, { act } from "react";
import { ChiffresPanel } from "../src/components/ChiffresPanel";
import type { ChiffresSummary } from "../src/types";
const dom = new JSDOM("<!doctype html><div id='root'></div>", { url: "http://localhost:5173" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const row = (value: number | null) => ({ employee_id: "staff", employee_name: "Emma", soins: value, ventes: 0, contrats: 0, pourboires: 0, moyenne: value, total: value, tickets: 1, prestations: 1 });
const report: ChiffresSummary = { institute_id: "inst", generated_at: "2026-10-06T10:00:00Z", period_start: "2026-10-06T00:00:00Z", period_end: "2026-10-07T00:00:00Z", rows: [row(null)], totals: row(null), currency: null, unknown_currency_tickets: 1, currency_groups: [{ currency: "CHF", rows: [row(10.45)], totals: row(10.45) }, { currency: "EUR", rows: [row(20.10)], totals: row(20.10) }] };

test("report selects currency totals separately and signals unpriced historical units", async () => {
  const root = createRoot(document.getElementById("root")!);
  try {
    await act(async () => root.render(<ChiffresPanel chiffres={report} onRefresh={() => {}} />));
    assert.match(document.body.textContent!, /10[.,]45/);
    assert.doesNotMatch(document.body.textContent!, /20[.,]10/);
    assert.match(document.body.textContent!, /1 ticket\(s\) sans devise/);
    const select = document.querySelector<HTMLSelectElement>("select")!;
    await act(async () => { select.value = "EUR"; select.dispatchEvent(new dom.window.Event("change", { bubbles: true })); });
    assert.match(document.body.textContent!, /20[.,]10/);
    assert.doesNotMatch(document.body.textContent!, /10[.,]45/);
  } finally { await act(async () => root.unmount()); }
});

test("unknown currency never renders an unlabelled legacy monetary total as zero or a sum", async () => {
  const root = createRoot(document.getElementById("root")!);
  try {
    await act(async () => root.render(<ChiffresPanel chiffres={{ ...report, currency_groups: [], rows: [row(999)], totals: row(999) }} onRefresh={() => {}} />));
    assert.doesNotMatch(document.body.textContent!, /999/);
    assert.match(document.body.textContent!, /Devise non connue/);
    assert.match(document.body.textContent!, /—/);
  } finally { await act(async () => root.unmount()); }
});
