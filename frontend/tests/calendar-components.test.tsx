import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import React, { act } from "react";
import { AppointmentPanel } from "../src/components/AppointmentPanel";
import { PlanningBoard } from "../src/components/PlanningBoard";
const dom = new JSDOM("<!doctype html><div id='root'></div>", { url: "http://localhost:5173" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document,
  sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const service = { id: "svc", category_id: "cat", name: "Soin", duration_min: 30, requires_machine: false, requires_appointment: false, status: "active" };
const employee = { id: "emp", institute_id: "inst", first_name: "Test", status: "available" };
const booking = { id: "booking", institute_id: "inst", employee_id: "emp", service_id: "svc", customer_name: "Client",
  start_time: "2026-10-25T01:30:12.123456Z", end_time: "2026-10-25T02:00:00Z", status: "scheduled" };
function button(text: string) { return [...document.querySelectorAll<HTMLButtonElement>("button")].find(item => item.textContent === text)!; }
async function fill(selector: string, value: string) {
  await act(async () => { const element = document.querySelector<HTMLInputElement | HTMLSelectElement>(selector)!;
    const prototype = element.tagName === "SELECT" ? window.HTMLSelectElement.prototype : window.HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(prototype, "value")!.set!.call(element, value);
    element.dispatchEvent(new window.Event(element.tagName === "SELECT" ? "change" : "input", { bubbles: true })); });
}

test("editing a repeated institute hour preserves the original precise instant and supports an explicit other fold", async () => {
  const root = createRoot(document.getElementById("root")!); const writes: string[] = [];
  const props = { instituteId: "inst", timezone: "Europe/Zurich", employees: [employee], services: [service], appointments: [booking],
    async onCreateAppointment() { assert.fail("Must edit"); }, async onUpdateAppointment(_id: string, payload: any) { writes.push(payload.start_time); }, async onAppointmentAction() {} };
  try {
    await act(async () => root.render(<AppointmentPanel {...props} />));
    assert.match(document.querySelector(".appointment-card")!.textContent!, /02:30/);
    await act(async () => button("Modifier").click());
    assert.equal(document.querySelector<HTMLInputElement>('input[type="time"]')!.value, "02:30");
    assert.equal(document.querySelector<HTMLSelectElement>(".appointment-occurrence select")!.value, "2026-10-25T01:30:00.000Z");
    await act(async () => button("Enregistrer les modifications").click());
    assert.equal(writes[0], booking.start_time);
    await act(async () => button("Modifier").click());
    await fill(".appointment-occurrence select", "2026-10-25T00:30:00.000Z");
    await act(async () => button("Enregistrer les modifications").click());
    assert.equal(writes[1], "2026-10-25T00:30:00.000Z");
  } finally { await act(async () => root.unmount()); }
});

test("booking rejects skipped/unselected repeated hours, then sends the selected institute instant", async () => {
  const root = createRoot(document.getElementById("root")!); const writes: any[] = [];
  const props = { instituteId: "inst", timezone: "Europe/Zurich", employees: [employee], services: [service], appointments: [],
    async onCreateAppointment(payload: any) { writes.push(payload); }, async onAppointmentAction() {} };
  try {
    await act(async () => root.render(<AppointmentPanel {...props} />));
    await fill('input[placeholder="Ex. Mme Dupont"]', "Client");
    await fill('input[type="date"]', "2026-03-29"); await fill('input[type="time"]', "02:30");
    await act(async () => button("Créer RDV").click());
    assert.equal(writes.length, 0); assert.match(document.querySelector('[role="alert"]')!.textContent!, /n'existe pas/);
    await fill('input[type="date"]', "2026-10-25");
    await act(async () => button("Créer RDV").click());
    assert.equal(writes.length, 0); assert.match(document.querySelector('[role="alert"]')!.textContent!, /occurrence/);
    await fill(".appointment-occurrence select", "2026-10-25T01:30:00.000Z");
    await act(async () => button("Créer RDV").click());
    assert.equal(writes[0].start_time, "2026-10-25T01:30:00.000Z");
    assert.equal(writes[0].institute_id, "inst"); assert.ok(writes[0].idempotency_key);
    await act(async () => root.render(<AppointmentPanel {...props} instituteId="other" timezone="UTC" />));
    assert.equal(document.querySelector<HTMLInputElement>('input[placeholder="Ex. Mme Dupont"]')!.value, "");
    assert.equal(document.querySelector(".appointment-occurrence"), null);
  } finally { await act(async () => root.unmount()); }
});

test("planning date, cursor, appointment position and labels use the institute on an LA workstation", async () => {
  const root = createRoot(document.getElementById("root")!), previousDate = globalThis.Date, previousZone = process.env.TZ;
  const fixed = previousDate.parse("2026-10-06T22:30:00Z");
  class FixedDate extends previousDate { constructor(value?: string | number) { super(value === undefined ? fixed : value); } static now() { return fixed; } }
  process.env.TZ = "America/Los_Angeles"; globalThis.Date = FixedDate as DateConstructor;
  try {
    await act(async () => root.render(<PlanningBoard timezone="Europe/Zurich" employees={[employee]} services={[service]}
      appointments={[{ ...booking, start_time: "2026-10-06T22:45:00Z", end_time: "2026-10-06T23:15:00Z" }]}
      onFinishSession={() => {}} onFinishAndOpenCheckout={() => {}} onExtendSession={() => {}}
      onChangeEmployeeStatus={() => {}} onFinishActiveEmployeeSession={() => {}} />));
    assert.match(document.querySelector(".planning-zone")!.textContent!, /07\.10\.2026/);
    assert.equal(document.querySelector<HTMLElement>(".row-now-cursor")!.style.left, "10%");
    const block = document.querySelector<HTMLElement>(".appointment-block")!;
    assert.equal(block.style.left, "15%"); assert.equal(block.style.width, "10%");
    assert.match(block.textContent!, /00:45/);
  } finally { globalThis.Date = previousDate; if (previousZone === undefined) delete process.env.TZ; else process.env.TZ = previousZone; await act(async () => root.unmount()); }
});

test("pending booking confirmation keeps all authoring fields disabled until refresh completes", async () => {
  const root = createRoot(document.getElementById("root")!); let finish!: () => void;
  try {
    await act(async () => root.render(<AppointmentPanel instituteId="inst" timezone="Europe/Zurich" employees={[employee]} services={[service]} appointments={[]}
      onCreateAppointment={() => new Promise<void>(resolve => { finish = resolve; })} onAppointmentAction={async () => {}} />));
    await fill('input[placeholder="Ex. Mme Dupont"]', "Client");
    await act(async () => button("Créer RDV").click());
    assert.equal(document.querySelector<HTMLFieldSetElement>("fieldset")!.disabled, true);
    assert.equal(document.querySelector<HTMLInputElement>('input[type="time"]')!.matches(":disabled"), true);
    await act(async () => finish());
    assert.equal(document.querySelector<HTMLFieldSetElement>("fieldset")!.disabled, false);
    assert.equal(document.querySelector<HTMLInputElement>('input[placeholder="Ex. Mme Dupont"]')!.value, "");
  } finally { await act(async () => root.unmount()); }
});

test("a pending appointment action cannot overlap a second booking mutation", async () => {
  const root = createRoot(document.getElementById("root")!); let finish!: () => void; let creations = 0;
  try {
    await act(async () => root.render(<AppointmentPanel instituteId="inst" timezone="Europe/Zurich" employees={[employee]} services={[service]} appointments={[booking]}
      onCreateAppointment={async () => { creations++; }} onAppointmentAction={() => new Promise<void>(resolve => { finish = resolve; })} />));
    await fill('input[placeholder="Ex. Mme Dupont"]', "Next client");
    await act(async () => button("Confirmer").click());
    assert.equal(button("Créer RDV").disabled, true);
    await act(async () => button("Créer RDV").click());
    assert.equal(creations, 0);
    await act(async () => finish());
    assert.equal(button("Créer RDV").disabled, false);
    assert.equal(document.querySelector<HTMLInputElement>('input[placeholder="Ex. Mme Dupont"]')!.value, "Next client");
  } finally { await act(async () => root.unmount()); }
});
