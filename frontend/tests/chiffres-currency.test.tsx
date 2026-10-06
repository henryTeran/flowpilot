import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import React, { act } from "react";
import { ChiffresPanel } from "../src/components/ChiffresPanel";
import type { ChiffresSummary } from "../src/types";
const dom = new JSDOM("<!doctype html><div id='root'></div>", { url: "http://localhost:5173" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const row = (value: string | null) => ({ employee_id: "staff", employee_name: "Emma", soins: value, ventes: "0.00", contrats: "0.00", pourboires: "0.00", moyenne: value, total: value, tickets: 1, prestations: 1 });
const report: ChiffresSummary = { institute_id: "inst", generated_at: "2026-10-06T10:00:00Z", period_start: "2026-10-06T00:00:00Z", period_end: "2026-10-07T00:00:00Z", rows: [row(null)], totals: row(null), currency: null, unknown_currency_tickets: 1, currency_groups: [{ currency: "CHF", rows: [row("10.45")], totals: row("10.45") }, { currency: "EUR", rows: [row("20.10")], totals: row("20.10") }] };

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
    await act(async () => root.render(<ChiffresPanel chiffres={{ ...report, currency_groups: [], rows: [row("999.00")], totals: row("999.00") }} onRefresh={() => {}} />));
    assert.doesNotMatch(document.body.textContent!, /999/);
    assert.match(document.body.textContent!, /Devise non connue/);
    assert.match(document.body.textContent!, /—/);
  } finally { await act(async () => root.unmount()); }
});

test("large monetary text preserves the recorded cents without a Number conversion", async () => {
  const root = createRoot(document.getElementById("root")!);
  try {
    await act(async () => root.render(<ChiffresPanel chiffres={{ ...report, currency: "CHF", currency_groups: [], rows: [row("90071992547409.93")], totals: row("90071992547409.93") }} onRefresh={() => {}} />));
    assert.match(document.body.textContent!, /90\u202f071\u202f992\u202f547\u202f409,93/);
    assert.doesNotMatch(document.body.textContent!, /409,94|409,92/);
  } finally { await act(async () => root.unmount()); }
});

test("loading and wrong-institute data hide prior financial facts; institute changes reset currency", async () => {
  const root = createRoot(document.getElementById("root")!);
  try {
    await act(async () => root.render(<ChiffresPanel instituteId="inst" chiffres={report} onRefresh={() => {}} />));
    const select = document.querySelector<HTMLSelectElement>("select")!;
    await act(async () => { select.value = "EUR"; select.dispatchEvent(new dom.window.Event("change", { bubbles: true })); });
    assert.match(document.body.textContent!, /20,10/);
    await act(async () => root.render(<ChiffresPanel instituteId="inst" chiffres={report} loading onRefresh={() => {}} />));
    assert.doesNotMatch(document.body.textContent!, /20,10|10,45|Emma/);
    await act(async () => root.render(<ChiffresPanel instituteId="" chiffres={report} onRefresh={() => {}} />));
    assert.doesNotMatch(document.body.textContent!, /20,10|10,45|Emma/);
    assert.match(document.body.textContent!, /Chiffres non disponibles/);
    await act(async () => root.render(<ChiffresPanel instituteId="other" chiffres={report} onRefresh={() => {}} />));
    assert.doesNotMatch(document.body.textContent!, /20,10|10,45|Emma/);
    await act(async () => root.render(<ChiffresPanel instituteId="other" chiffres={{ ...report, institute_id: "other" }} onRefresh={() => {}} />));
    assert.equal(document.querySelector<HTMLSelectElement>("select")!.value, "CHF");
    assert.match(document.body.textContent!, /10,45/);
  } finally { await act(async () => root.unmount()); }
});
