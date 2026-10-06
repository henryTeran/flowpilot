import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import React, { act } from "react";
import { setAccessToken } from "../src/api/session";
const dom = new JSDOM("<!doctype html><div id='root'></div>", { url: "http://localhost:5173" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const { default: App } = await import("../src/App");
const response = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { "Content-Type": "application/json" } });
const report = (amount: string) => {
  const row = { employee_id: "staff", employee_name: "Emma", soins: amount, ventes: "0.00", contrats: "0.00", pourboires: "0.00", moyenne: amount, total: amount, tickets: 1, prestations: 1 };
  return { institute_id: "inst", currency: "CHF", currency_groups: [], unknown_currency_tickets: 0, generated_at: "2026-10-06T10:00:00Z", period_start: "2026-10-06T00:00:00Z", period_end: "2026-10-07T00:00:00Z", rows: [row], totals: row };
};

test("late manual report cannot overwrite a newer operational read or revive data after its failure", async () => {
  const root = createRoot(document.getElementById("root")!), originalFetch = globalThis.fetch, originalSocket = globalThis.WebSocket;
  const originalInterval = window.setInterval, originalClear = window.clearInterval;
  let operationalTick!: () => void;
  window.setInterval = ((callback: () => void, delay: number) => { if (delay === 10000) operationalTick = callback; return 1; }) as typeof window.setInterval;
  window.clearInterval = () => {};
  class Socket { static OPEN = 1; readyState = 0; close() {} send() {} }
  globalThis.WebSocket = Socket as unknown as typeof WebSocket;
  setAccessToken("session");
  let defer = false;
  const pending: Array<(value: Response) => void> = [];
  globalThis.fetch = async input => {
    const path = new URL(String(input)).pathname.replace("/api/v1", "");
    if (path === "/tickets/chiffres") return defer ? new Promise<Response>(resolve => pending.push(resolve)) : response(report("10.00"));
    if (path === "/institutes") return response([{ id: "inst", name: "Institute", city: "Test", timezone: "Europe/Berlin", status: "active" }]);
    if (path.endsWith("/today")) return response({ institute_id: "inst", generated_at: "2026-10-06T10:00:00Z", rows: [] });
    if (path.endsWith("/availability")) return response({ institute_id: "inst", employees: [], active_sessions: 0, waiting_tickets: 0 });
    return response([]);
  };
  try {
    await act(async () => root.render(<App />));
    await act(async () => document.querySelector<HTMLButtonElement>('button[aria-label="Pilotage"]')!.click());
    assert.match(document.querySelector(".bm-chiffres-screen")!.textContent!, /10,00/);
    defer = true;
    const refresh = () => document.querySelector<HTMLButtonElement>(".bm-chiffres-header button")!.click();
    await act(async () => refresh());
    await act(async () => operationalTick());
    assert.equal(pending.length, 2);
    await act(async () => pending[1](response(report("21.10"))));
    assert.match(document.querySelector(".bm-chiffres-screen")!.textContent!, /21,10/);
    await act(async () => pending[0](response(report("90.00"))));
    assert.doesNotMatch(document.querySelector(".bm-chiffres-screen")!.textContent!, /90,00/);
    assert.match(document.querySelector(".bm-chiffres-screen")!.textContent!, /21,10/);
    await act(async () => refresh());
    await act(async () => operationalTick());
    await act(async () => pending[3](response({ detail: "Report unavailable" }, 503)));
    await act(async () => pending[2](response(report("99.00"))));
    assert.doesNotMatch(document.querySelector(".bm-chiffres-screen")!.textContent!, /21,10|99,00/);
    assert.match(document.querySelector(".bm-chiffres-screen")!.textContent!, /Chiffres non disponibles/);
    assert.equal(document.querySelector<HTMLButtonElement>(".bm-chiffres-header button")!.disabled, false);
    await act(async () => refresh());
    await act(async () => operationalTick());
    await act(async () => pending[4](response(report("88.00"))));
    assert.equal(document.querySelector<HTMLButtonElement>(".bm-chiffres-header button")!.disabled, true);
    assert.doesNotMatch(document.querySelector(".bm-chiffres-screen")!.textContent!, /88,00/);
    await act(async () => pending[5](response(report("31.15"))));
    assert.match(document.querySelector(".bm-chiffres-screen")!.textContent!, /31,15/);
    assert.equal(document.querySelector<HTMLButtonElement>(".bm-chiffres-header button")!.disabled, false);
  } finally {
    await act(async () => root.unmount()); globalThis.fetch = originalFetch; globalThis.WebSocket = originalSocket;
    window.setInterval = originalInterval; window.clearInterval = originalClear; setAccessToken(null);
  }
});
