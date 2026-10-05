import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import React, { act } from "react";
import { NewTicketWorkflow } from "../src/components/NewTicketWorkflow";
import { apiGet, apiPost } from "../src/api/client";
import { setAccessToken } from "../src/api/session";
import { useAssignmentOptions } from "../src/features/useAssignmentOptions";
import { QueuePanel } from "../src/components/QueuePanel";
import { AppointmentPanel } from "../src/components/AppointmentPanel";
import type { QueueTicket, AssignmentOption } from "../src/types";

const dom = new JSDOM("<!doctype html><div id='root'></div>", { url: "http://localhost:5173" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document,
  sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const category = { id: "cat", name: "Épilation", code: "EPILATION" };
const service = { id: "svc", category_id: "cat", name: "Aisselles", duration_min: 10,
  price_passage: 15, requires_machine: false, requires_appointment: false, status: "active" };

const assignmentTicket: QueueTicket = { id: "ticket", institute_id: "inst", ticket_number: "T-001",
  status: "waiting", arrival_time: "2026-10-05T10:00:00Z", standard_duration_minutes: 45, lines: [] };
const availableOption: AssignmentOption = { employee_id: "emp", employee_name: "Test", assignable: true,
  reason: "available from 10:00", available_from: "2026-10-05T10:00:00Z", available_until: null,
  service_duration_minutes: 45 };

function emptyGiftTender(ticket: QueueTicket) {
  return new Response(JSON.stringify({ ticket_id: ticket.id, currency: ticket.currency || null,
    total: ticket.total_amount || 0, gift_amount: "0", remaining_due: ticket.total_amount || 0,
    remainder_amount: "0", remainder_method: null, allocations: [] }), { headers: { "Content-Type": "application/json" } });
}

test("commercial validity dates preserve UTC across SQLite and PostgreSQL response formats", async () => {
  const { readUtcDate } = await import("../src/api/dates");
  assert.equal(readUtcDate("2026-10-05T23:30:00").getTime(), Date.parse("2026-10-05T23:30:00Z"));
  assert.equal(readUtcDate("2026-10-06T01:30:00+02:00").getTime(), Date.parse("2026-10-05T23:30:00Z"));
});

test("booking editor retries failed movement and exposes confirmation only for scheduled bookings", async () => {
  const root = createRoot(document.getElementById("root")!);
  const appointment = { id: "booking", institute_id: "inst", employee_id: "emp", service_id: "svc",
    customer_name: "Test client", start_time: "2026-10-05T10:00:00Z", end_time: "2026-10-05T10:20:00Z", status: "scheduled" };
  let attempts = 0;
  const actions: string[] = [];
  const props = { instituteId: "inst", employees: [{ id: "emp", institute_id: "inst", first_name: "Test", status: "available" }],
    services: [service], appointments: [appointment], async onCreateAppointment() { assert.fail("Editing must update"); },
    async onUpdateAppointment(id: string, payload: any) {
      assert.equal(id, "booking");
      assert.equal(payload.customer_name, "Test client");
      assert.equal(payload.employee_id, "emp");
      assert.equal("institute_id" in payload, false);
      if (++attempts === 1) throw new Error("Room conflict");
    }, async onAppointmentAction(id: string, action: string) { actions.push(`${id}:${action}`); } };
  const find = (label: string) => [...document.querySelectorAll<HTMLButtonElement>("button")].find(item => item.textContent === label)!;
  try {
    await act(async () => root.render(<AppointmentPanel {...props} />));
    await act(async () => find("Confirmer").click());
    assert.deepEqual(actions, ["booking:confirm"]);
    await act(async () => find("Modifier").click());
    await act(async () => find("Enregistrer les modifications").click());
    assert.match(document.querySelector("[role='alert']")!.textContent!, /Room conflict/);
    assert.ok(find("Enregistrer les modifications"));
    await act(async () => find("Enregistrer les modifications").click());
    assert.equal(attempts, 2);
    assert.ok(find("Créer RDV"));
    await act(async () => root.render(<AppointmentPanel {...props} appointments={[{ ...appointment, status: "confirmed" }]} />));
    assert.equal(find("Confirmer"), undefined);
  } finally { await act(async () => root.unmount()); }
});

test("booking creation retains its replay key after failure", async () => {
  const root = createRoot(document.getElementById("root")!);
  const keys: string[] = [];
  const props = { instituteId: "inst", employees: [{ id: "emp", institute_id: "inst", first_name: "Test", status: "available" }],
    services: [service], appointments: [], async onCreateAppointment(payload: any) {
      keys.push(payload.idempotency_key);
      if (keys.length === 1) throw new Error("Lost response");
    }, async onAppointmentAction() {} };
  const enterName = async () => act(async () => {
    const input = document.querySelector<HTMLInputElement>('input[placeholder="Ex. Mme Dupont"]')!;
    Object.getOwnPropertyDescriptor(dom.window.HTMLInputElement.prototype, "value")!.set!.call(input, "Test client");
    input.dispatchEvent(new dom.window.Event("input", { bubbles: true }));
  });
  const create = () => [...document.querySelectorAll<HTMLButtonElement>("button")].find(item => item.textContent === "Créer RDV")!;
  try {
    await act(async () => root.render(<AppointmentPanel {...props} />));
    await enterName();
    await act(async () => create().click());
    await act(async () => create().click());
    assert.equal(keys.length, 2);
    assert.ok(keys[0]);
    assert.equal(keys[0], keys[1]);
    await enterName();
    await act(async () => create().click());
    assert.notEqual(keys[2], keys[1]);
  } finally { await act(async () => root.unmount()); }
});

test("queue actions use duration-aware feasibility, fail closed while loading, and offer retry", async () => {
  const root = createRoot(document.getElementById("root")!);
  let retries = 0;
  const props = { tickets: [assignmentTicket], services: [service], categories: [category],
    employees: [{ id: "emp", institute_id: "inst", first_name: "Test", status: "available" }],
    selectedCategoryId: "cat", selectedServiceId: "svc", selectedTicketId: "ticket", selectedEmployeeId: "emp",
    ticketServiceMap: { ticket: ["svc"] }, onCategoryChange() {}, onServiceChange() {}, onTicketChange() {},
    onEmployeeChange() {}, onCreateTicket() {}, onAssignTicket() {}, onUnassignTicket() {}, onStartSession() {},
    onCancelTicket() {}, onFinishActiveEmployeeSession() {}, onChangeEmployeeStatus() {}, onStartCheckout() {} };
  try {
    await act(async () => root.render(<QueuePanel {...props} assignment={{ status: "loading", options: [], retry() {} }} />));
    assert.equal(button("Affecter").disabled, true);
    assert.equal(button("Démarrer séance").disabled, true);
    assert.match(document.body.textContent || "", /Vérification des disponibilités/);
    await act(async () => root.render(<QueuePanel {...props} assignment={{ status: "ready",
      options: [{ ...availableOption, assignable: false, reason: "service doesn't fit (45min) before appointment at 10:20" }], retry() {} }} />));
    assert.equal(button("Démarrer séance").disabled, true);
    assert.match(document.body.textContent || "", /La séance ne tient pas avant le prochain rendez-vous/);
    await act(async () => root.render(<QueuePanel {...props} assignment={{ status: "ready", options: [availableOption], retry() {} }} />));
    assert.equal(button("Affecter").disabled, false);
    assert.equal(button("Démarrer séance").disabled, false);
    assert.match(document.body.textContent || "", /45 min réservées/);
    await act(async () => root.render(<QueuePanel {...props} assignment={{ status: "error", options: [], retry() { retries++; } }} />));
    assert.equal(button("Démarrer séance").disabled, true);
    await act(async () => button("Réessayer").click());
    assert.equal(retries, 1);
  } finally { await act(async () => root.unmount()); }
});

test("assignment hook ignores stale ticket and tenant responses", async () => {
  const originalFetch = globalThis.fetch;
  const pending: Array<(response: Response) => void> = [];
  const urls: string[] = [];
  globalThis.fetch = async (url) => {
    urls.push(String(url));
    return new Promise<Response>((resolve) => pending.push(resolve));
  };
  function Probe({ institute, ticket }: { institute: string; ticket: QueueTicket }) {
    const state = useAssignmentOptions(institute, ticket);
    return <div data-status={state.status}>{state.options.map((option) => option.employee_id).join(",")}</div>;
  }
  const root = createRoot(document.getElementById("root")!);
  const resolve = (index: number, employee: string) => pending[index](new Response(JSON.stringify({
    options: [{ ...availableOption, employee_id: employee }],
  }), { headers: { "Content-Type": "application/json" } }));
  try {
    await act(async () => root.render(<Probe institute="inst" ticket={assignmentTicket} />));
    await act(async () => root.render(<Probe institute="other" ticket={{ ...assignmentTicket, id: "second", institute_id: "other" }} />));
    assert.match(urls[1], /second\/assignment-options\?institute_id=other/);
    await act(async () => resolve(1, "current"));
    assert.equal(document.querySelector("[data-status]")?.getAttribute("data-status"), "ready");
    assert.match(document.body.textContent || "", /current/);
    await act(async () => resolve(0, "stale"));
    assert.doesNotMatch(document.body.textContent || "", /stale/);
    assert.match(document.body.textContent || "", /current/);
  } finally {
    await act(async () => root.unmount());
    globalThis.fetch = originalFetch;
  }
});

test("late operational response from a prior institute cannot overwrite the planning board", async () => {
  const { default: App } = await import("../src/App");
  const originalFetch = globalThis.fetch;
  const originalWebSocket = globalThis.WebSocket;
  const pending: Array<() => void> = [];
  class FakeSocket { readyState = 0; close() {} send() {} }
  globalThis.WebSocket = FakeSocket as unknown as typeof WebSocket;
  globalThis.fetch = async url => {
    const parsed = new URL(String(url));
    const path = parsed.pathname.replace("/api/v1", "");
    const institute = parsed.searchParams.get("institute_id") || (/\/institutes\/(one|two)\//.exec(path)?.[1]);
    let payload: any = [];
    if (path === "/institutes") payload = ["one", "two"].map(id => ({ id, name: id, city: "Test", timezone: "Europe/Berlin", status: "active" }));
    else if (path.endsWith("/today")) payload = { institute_id: institute, rows: [{ employee_id: `${institute}-emp`, employee_name: `${institute} board`, employee_status: "available", sessions: [] }] };
    else if (path.endsWith("/availability")) payload = { institute_id: institute, employees: [], active_sessions: 0, waiting_tickets: 0 };
    else if (path === "/tickets/chiffres") payload = { institute_id: institute, rows: [], totals: { total: 0, soins: 0, ventes: 0, contrats: 0, pourboires: 0 } };
    const response = () => new Response(JSON.stringify(payload), { headers: { "Content-Type": "application/json" } });
    if (institute === "one") return await new Promise<Response>(resolve => pending.push(() => resolve(response())));
    return response();
  };
  const root = createRoot(document.getElementById("root")!);
  try {
    await act(async () => root.render(<App />));
    assert.ok(pending.length >= 6);
    const select = document.querySelector<HTMLSelectElement>(".bm-top-controls select")!;
    await act(async () => { select.value = "two"; select.dispatchEvent(new dom.window.Event("change", { bubbles: true })); });
    assert.match(document.body.textContent!, /two board/);
    await act(async () => pending.forEach(resolve => resolve()));
    assert.match(document.body.textContent!, /two board/);
    assert.doesNotMatch(document.body.textContent!, /one board/);
  } finally {
    await act(async () => root.unmount());
    globalThis.fetch = originalFetch;
    globalThis.WebSocket = originalWebSocket;
  }
});

for (const changeInstitute of [false, true]) {
test(changeInstitute ? "changing institute during assignment prevents the obsolete start action"
  : "selecting a ticket and starting uses the feasible employee in two actions", async () => {
  const { default: App } = await import("../src/App");
  const originalFetch = globalThis.fetch;
  const originalWebSocket = globalThis.WebSocket;
  const writes: Array<{ path: string; body: Record<string, string> }> = [];
  const selected = { ...assignmentTicket, lines: [{ id: "line", ticket_id: "ticket", service_id: "svc",
    quantity: 1, duration_minutes: 45, unit_price: 15, total: 15, revenue_category: "care", status: "pending" }] };
  let started = false;
  let resolveAssignment: (() => void) | undefined;
  const employees = [{ id: "blocked", institute_id: "inst", first_name: "Busy soon", status: "available", skills: [] },
    { id: "emp", institute_id: "inst", first_name: "Available", status: "available", skills: [] }];
  class FakeSocket { static OPEN = 1; readyState = 0; close() {} send() {} }
  globalThis.WebSocket = FakeSocket as unknown as typeof WebSocket;
  globalThis.fetch = async (url, init) => {
    const path = new URL(String(url)).pathname.replace("/api/v1", "");
    let payload: unknown = [];
    if (init?.method === "PATCH" || init?.method === "POST") {
      writes.push({ path, body: JSON.parse(String(init.body)) });
      if (path === "/planning/sessions/start") started = true;
      payload = selected;
      if (changeInstitute && path.endsWith("/assign")) {
        return await new Promise<Response>(resolve => { resolveAssignment = () => resolve(new Response(JSON.stringify(selected),
          { headers: { "Content-Type": "application/json" } })); });
      }
    } else if (path === "/institutes") payload = ["inst", "other"].map(id => ({ id, name: id, city: "Test", timezone: "Europe/Berlin", status: "active" }));
    else if (path === "/services/categories") payload = [category];
    else if (path === "/services/catalog") payload = [service];
    else if (path === "/employees") payload = employees;
    else if (path === "/tickets/waiting") payload = started ? [] : [selected];
    else if (path.endsWith("/assignment-options")) payload = { options: [
      { ...availableOption, employee_id: "blocked", assignable: false, reason: "service doesn't fit before appointment" }, availableOption,
    ] };
    else if (path.endsWith("/today")) payload = { institute_id: "inst", generated_at: "2026-10-05T10:00:00Z", rows: [] };
    else if (path.endsWith("/availability")) payload = { institute_id: "inst", employees: [], active_sessions: 0, waiting_tickets: 1 };
    else if (path === "/tickets/chiffres") payload = { institute_id: "inst", rows: [], totals: { total: 0, soins: 0, ventes: 0, contrats: 0, pourboires: 0 } };
    return new Response(JSON.stringify(payload), { headers: { "Content-Type": "application/json" } });
  };
  const root = createRoot(document.getElementById("root")!);
  try {
    await act(async () => root.render(<App />));
    const ticket = document.querySelector<HTMLElement>(".compact-ticket");
    assert.ok(ticket);
    await act(async () => ticket.click());
    assert.ok(document.querySelector("[role='dialog']"));
    assert.equal(button("Démarrer séance").disabled, false);
    await act(async () => button("Démarrer séance").click());
    if (changeInstitute) {
      assert.ok(resolveAssignment);
      const institute = document.querySelector<HTMLSelectElement>(".bm-top-controls select")!;
      await act(async () => { institute.value = "other"; institute.dispatchEvent(new dom.window.Event("change", { bubbles: true })); });
      await act(async () => resolveAssignment!());
      assert.deepEqual(writes.map(request => request.path), ["/tickets/ticket/assign"]);
      assert.equal(document.querySelector("[role='dialog']"), null);
    } else {
      assert.deepEqual(writes.map((request) => request.path), ["/tickets/ticket/assign", "/planning/sessions/start"]);
      assert.equal(writes[1].body.employee_id, "emp");
    }
    assert.equal(writes[0].body.employee_id, "emp");
  } finally {
    await act(async () => root.unmount());
    globalThis.fetch = originalFetch;
    globalThis.WebSocket = originalWebSocket;
  }
});
}

test("finishing a booking opens its linked checkout after cashier identification", async () => {
  const { default: App } = await import("../src/App");
  const originalFetch = globalThis.fetch;
  const originalWebSocket = globalThis.WebSocket;
  class FakeSocket { readyState = 0; close() {} send() {} }
  globalThis.WebSocket = FakeSocket as unknown as typeof WebSocket;
  const employee = { id: "emp", institute_id: "inst", first_name: "Cashier", status: "available", skills: [] };
  const booking = { id: "booking", institute_id: "inst", employee_id: "emp", service_id: "svc",
    customer_name: "Booking client", start_time: "2026-10-05T10:00:00Z", end_time: "2026-10-05T10:10:00Z",
    status: "in_progress", checkout_ticket_id: null as string | null };
  const ticket = { ...assignmentTicket, id: "booking-checkout", status: "ready_for_checkout",
    total_amount: 15, lines: [{ id: "line", ticket_id: "booking-checkout", service_id: "svc", quantity: 1,
      duration_minutes: 10, unit_price: 15, total: 15, revenue_category: "care", performed_by_employee_id: "emp", status: "completed" }] };
  const writes: string[] = [];
  globalThis.fetch = async (url, init) => {
    const path = new URL(String(url)).pathname.replace("/api/v1", "");
    let payload: any = [];
    if (init?.method === "PATCH") {
      writes.push(path);
      if (path === "/appointments/booking/complete") { booking.status = "completed"; booking.checkout_ticket_id = ticket.id; payload = booking; }
      else if (path === `/tickets/${ticket.id}/checkout/start`) { ticket.status = "in_checkout"; payload = ticket; }
    } else if (path === "/institutes") payload = [{ id: "inst", name: "Test", city: "Test", timezone: "Europe/Berlin", status: "active" }];
    else if (path === "/employees") payload = [employee];
    else if (path === "/services/categories") payload = [category];
    else if (path === "/services/catalog") payload = [service];
    else if (path === "/appointments") payload = [booking];
    else if (path === "/tickets/waiting") payload = booking.checkout_ticket_id ? [ticket] : [];
    else if (path.endsWith("/today")) payload = { institute_id: "inst", rows: [] };
    else if (path.endsWith("/availability")) payload = { institute_id: "inst", employees: [], active_sessions: 0, waiting_tickets: 0 };
    else if (path === "/tickets/chiffres") payload = { institute_id: "inst", rows: [], totals: { total: 0, soins: 0, ventes: 0, contrats: 0, pourboires: 0 } };
    return new Response(JSON.stringify(payload), { headers: { "Content-Type": "application/json" } });
  };
  const root = createRoot(document.getElementById("root")!);
  try {
    await act(async () => root.render(<App />));
    await act(async () => button("RDV sous appel").click());
    await act(async () => button("Terminer").click());
    assert.ok(document.querySelector(".bm-identify-screen"));
    await act(async () => document.querySelector<HTMLButtonElement>(".bm-identify-card")!.click());
    assert.deepEqual(writes, ["/appointments/booking/complete", `/tickets/${ticket.id}/checkout/start`]);
    assert.ok(document.querySelector(".bm-checkout-clone"));
    assert.match(document.body.textContent!, /Aisselles/);
  } finally {
    await act(async () => root.unmount());
    globalThis.fetch = originalFetch; globalThis.WebSocket = originalWebSocket;
  }
});

test("customer picker rejects obsolete search responses and retries creation with one intent", async () => {
  const { CustomerPicker } = await import("../src/components/CustomerPicker");
  const originalFetch = globalThis.fetch;
  const customer = { id: "customer_selected", institute_id: "inst", display_name: "Émilie Dupont", phone: "+41 79", created_at: "2026-10-05T10:00:00Z" };
  let oldSearch: (() => void) | undefined;
  const keys: string[] = [];
  const selections: any[] = [];
  globalThis.fetch = async (url, init) => {
    if (init?.method === "POST") {
      keys.push(JSON.parse(String(init.body)).idempotency_key);
      if (keys.length === 1) throw new Error("Lost response");
      return new Response(JSON.stringify(customer), { headers: { "Content-Type": "application/json" } });
    }
    if (new URL(String(url)).searchParams.get("q") === "Old") {
      return await new Promise<Response>(resolve => { oldSearch = () => resolve(new Response(JSON.stringify([
        { ...customer, id: "old", display_name: "Obsolete customer" },
      ]), { headers: { "Content-Type": "application/json" } })); });
    }
    return new Response(JSON.stringify([customer]), { headers: { "Content-Type": "application/json" } });
  };
  const root = createRoot(document.getElementById("root")!);
  const type = async (input: HTMLInputElement, value: string) => act(async () => {
    Object.getOwnPropertyDescriptor(dom.window.HTMLInputElement.prototype, "value")!.set!.call(input, value);
    input.dispatchEvent(new dom.window.Event("input", { bubbles: true }));
  });
  const settleSearch = async () => act(async () => { await new Promise(resolve => setTimeout(resolve, 250)); });
  try {
    await act(async () => root.render(<CustomerPicker instituteId="inst" onSelect={value => selections.push(value)} />));
    const search = document.querySelector<HTMLInputElement>('input[type="search"]')!;
    await type(search, "Old"); await settleSearch();
    assert.ok(oldSearch);
    await type(search, "Emilie"); await settleSearch();
    assert.match(document.body.textContent!, /Émilie Dupont/);
    await act(async () => oldSearch!());
    assert.doesNotMatch(document.body.textContent!, /Obsolete customer/);
    await act(async () => button("Émilie Dupont").click());
    assert.equal(selections[0].id, customer.id);
    await act(async () => button("Nouvelle cliente").click());
    const name = [...document.querySelectorAll("label")].find(label => label.textContent?.includes("Nom de la cliente"))!.querySelector("input")!;
    await type(name, "Émilie Dupont");
    await act(async () => button("Enregistrer la cliente").click());
    assert.match(document.querySelector("[role='alert']")!.textContent!, /Lost response/);
    await act(async () => button("Enregistrer la cliente").click());
    assert.equal(keys.length, 2); assert.equal(keys[0], keys[1]);
    assert.equal(selections[1].id, customer.id);
  } finally { await act(async () => root.unmount()); globalThis.fetch = originalFetch; }
});

test("named arrival submits the selected customer identity without displaying technical identifiers", async () => {
  const originalFetch = globalThis.fetch;
  const customer = { id: "customer_selected", institute_id: "inst", display_name: "Émilie Dupont", phone: "+41 79", created_at: "2026-10-05T10:00:00Z" };
  globalThis.fetch = async () => new Response(JSON.stringify([customer]), { headers: { "Content-Type": "application/json" } });
  const root = createRoot(document.getElementById("root")!);
  let submitted: any;
  try {
    await act(async () => root.render(<NewTicketWorkflow open instituteId="inst" categories={[category]} services={[service]}
      onClose={() => {}} onValidate={value => { submitted = value; }} />));
    await act(async () => button("Cliente").click());
    await act(async () => {
      const input = document.querySelector<HTMLInputElement>('input[type="search"]')!;
      Object.getOwnPropertyDescriptor(dom.window.HTMLInputElement.prototype, "value")!.set!.call(input, "Emilie");
      input.dispatchEvent(new dom.window.Event("input", { bubbles: true }));
    });
    await act(async () => { await new Promise(resolve => setTimeout(resolve, 250)); });
    await act(async () => button("Émilie Dupont").click());
    assert.doesNotMatch(document.body.textContent!, /customer_selected/);
    await act(async () => button("Prestations").click());
    await act(async () => button("Aisselles").click());
    await act(async () => button("Ajouter à la file").click());
    assert.equal(submitted.customer.customerId, customer.id);
    assert.equal(submitted.customer.lastName, customer.display_name);
  } finally { await act(async () => root.unmount()); globalThis.fetch = originalFetch; }
});

test("package wallet recovers a lost consumption response, blocks uncertain payment and reverses before checkout", async () => {
  const { CheckoutPanel } = await import("../src/components/CheckoutPanel");
  const originalFetch = globalThis.fetch;
  setAccessToken(`e30.${btoa(JSON.stringify({ role: "responsable_institut" }))}.signature`);
  let applied = false;
  let reversed = false;
  let reconciles = false;
  let intent = "";
  let posts = 0;
  const ticket: QueueTicket = { ...assignmentTicket, status: "ready_for_checkout", customer_id: "customer_selected", total_amount: 15,
    lines: [{ id: "line", ticket_id: "ticket", service_id: "svc", quantity: 1, duration_minutes: 10,
      unit_price: 15, total: 15, revenue_category: "care", performed_by_employee_id: "emp", status: "completed" }] };
  globalThis.fetch = async (url, init) => {
    const path = new URL(String(url)).pathname;
    if (path.includes("/memberships/")) return new Response("[]", { headers: { "Content-Type": "application/json" } });
    if (path.endsWith("/tenders")) return emptyGiftTender(ticket);
    let payload: any;
    if (init?.method === "POST") {
      posts++;
      if (path.endsWith("/consume")) { applied = true; intent = JSON.parse(String(init.body)).idempotency_key; throw new Error("Lost response"); }
      assert.ok(path.endsWith("/reverse")); reversed = true; payload = { id: "redemption", reversed_at: "now" };
    } else if (path.endsWith("/history")) payload = applied ? [{ id: "redemption", ticket_line_id: "line", reversed_at: reversed ? "now" : null }] : [];
    else if (path.includes("/customers/")) payload = { id: "customer_selected", display_name: "Émilie Dupont", phone: null };
    else payload = [{ id: "package", name: "Cure visage", service_id: "svc", remaining: applied && !reversed ? 1 : 2,
      usable_sessions: applied && !reversed ? 1 : 2, status: "active", expires_at: "2027-10-05T10:00:00Z" }];
    return new Response(JSON.stringify(payload), { headers: { "Content-Type": "application/json" } });
  };
  const root = createRoot(document.getElementById("root")!);
  const employee = { id: "emp", institute_id: "inst", first_name: "Cashier", skills: [], status: "available" };
  const render = () => root.render(<CheckoutPanel ticket={ticket} services={[service]} employees={[employee]} cashierEmployee={employee}
    selectedPaymentMethod="cb" onPaymentMethodChange={() => {}} onAddService={() => {}} onRemoveLine={() => {}}
    onPay={() => {}} onClose={() => {}} onRefresh={async () => {
      if (!reconciles) return false;
      ticket.total_amount = applied && !reversed ? 0 : 15;
      ticket.lines![0].total = ticket.total_amount;
      render();
      return true;
    }} />);
  try {
    await act(async () => render());
    assert.match(document.body.textContent!, /Émilie Dupont/);
    await act(async () => button("Utiliser 1 séance").click());
    assert.ok(intent); assert.equal(posts, 1);
    assert.equal(document.querySelector<HTMLButtonElement>(".bm-final-cash-button")!.disabled, true);
    reconciles = true;
    ticket.total_amount = 0;
    await act(async () => { render(); button("Actualiser les forfaits").click(); });
    assert.equal(document.querySelector<HTMLButtonElement>(".bm-final-cash-button")!.disabled, false);
    await act(async () => button("Annuler la consommation").click());
    assert.equal(posts, 2); assert.equal(reversed, true);
    assert.ok(button("Utiliser 1 séance"));
  } finally { await act(async () => root.unmount()); globalThis.fetch = originalFetch; setAccessToken(null); }
});

test("checkout identifies an anonymous customer and keeps uncertain identity changes from payment", async () => {
  const { CheckoutPanel } = await import("../src/components/CheckoutPanel");
  const originalFetch = globalThis.fetch;
  setAccessToken("identity-operator");
  let reconciles = false;
  let attached = false;
  let patches = 0;
  const ticket: QueueTicket = { ...assignmentTicket, status: "ready_for_checkout", total_amount: 15 };
  const customer = { id: "customer_checkout", display_name: "Selected checkout client", phone: null };
  globalThis.fetch = async (url, init) => {
    const path = new URL(String(url)).pathname;
    if (init?.method === "PATCH") {
      patches++; assert.ok(path.endsWith("/tickets/ticket/customer"));
      assert.deepEqual(JSON.parse(String(init.body)), { customer_id: customer.id });
      attached = true; throw new Error("Lost identity response");
    }
    if (path.endsWith("/tenders")) return emptyGiftTender(ticket);
    const value = path.includes("/customers/") ? path.endsWith(customer.id) ? customer : [customer] : [];
    return new Response(JSON.stringify(value), { headers: { "Content-Type": "application/json" } });
  };
  const root = createRoot(document.getElementById("root")!);
  const employee = { id: "emp", institute_id: "inst", first_name: "Cashier", status: "available" };
  const render = () => root.render(<CheckoutPanel ticket={ticket} services={[service]} employees={[employee]} cashierEmployee={employee}
    selectedPaymentMethod="cb" onPaymentMethodChange={() => {}} onAddService={() => {}} onRemoveLine={() => {}}
    onPay={() => {}} onClose={() => {}} onRefresh={async () => {
      if (!reconciles) return false;
      if (attached) ticket.customer_id = customer.id;
      render(); return true;
    }} />);
  try {
    await act(async () => render());
    await act(async () => button("Identifier la cliente").click());
    await act(async () => {
      const input = document.querySelector<HTMLInputElement>("input[type='search']")!;
      Object.getOwnPropertyDescriptor(dom.window.HTMLInputElement.prototype, "value")!.set!.call(input, "Selected");
      input.dispatchEvent(new dom.window.Event("input", { bubbles: true }));
    });
    await act(async () => { await new Promise(resolve => setTimeout(resolve, 250)); });
    await act(async () => button(customer.display_name).click());
    assert.equal(patches, 1);
    assert.equal(document.querySelector<HTMLButtonElement>(".bm-final-cash-button")!.disabled, true);
    assert.match(document.querySelector("[role='alert']")!.textContent!, /Lost identity response/);
    reconciles = true;
    await act(async () => button("Actualiser le ticket").click());
    assert.equal(patches, 1);
    assert.equal(document.querySelector<HTMLButtonElement>(".bm-final-cash-button")!.disabled, false);
    assert.match(document.body.textContent!, /Selected checkout client/);
    assert.ok(button("Changer de cliente"));
    await act(async () => { ticket.status = "paid"; render(); });
    assert.equal([...document.querySelectorAll("button")].some(item => item.textContent?.includes("Changer de cliente")), false);
  } finally { await act(async () => root.unmount()); globalThis.fetch = originalFetch; setAccessToken(null); }
});

test("commerce manager recovers plan creation and customer grants with the original replay keys", async () => {
  const { CommercePanel } = await import("../src/components/CommercePanel");
  const originalFetch = globalThis.fetch;
  setAccessToken(`e30.${btoa(JSON.stringify({ role: "responsable_institut" }))}.signature`);
  const plan = { id: "plan", name: "Cure test", service_id: "svc", sessions: 5, valid_days: 90 };
  const customer = { id: "customer_test", display_name: "Selected manager client", phone: null };
  const keys: Record<string, string[]> = { plan: [], issue: [] };
  let created = false;
  let issued = false;
  globalThis.fetch = async (url, init) => {
    const path = new URL(String(url)).pathname;
    if (path.endsWith("/snapshot")) return new Response(JSON.stringify({ balance: { customer_id: customer.id, points: 0, tier: null }, entries: [], redemptions: [] }), { headers: { "Content-Type": "application/json" } });
    if (path.includes("/memberships/")) return new Response("[]", { headers: { "Content-Type": "application/json" } });
    if (init?.method === "POST") {
      const payload = JSON.parse(String(init.body));
      const kind = path.endsWith("/package-plans") ? "plan" : "issue";
      keys[kind].push(payload.idempotency_key);
      if (kind === "plan") { assert.equal(payload.sessions, 5); created = true; }
      else { assert.equal(payload.customer_id, customer.id); assert.equal(payload.plan_id, plan.id); issued = true; }
      if (keys[kind].length === 1) throw new Error("Lost response");
      return new Response(JSON.stringify(kind === "plan" ? plan : { id: "package" }), { headers: { "Content-Type": "application/json" } });
    }
    const value = path.includes("/customers/") ? [customer] : path.endsWith("/package-plans") ? created ? [plan] : []
      : issued ? [{ id: "package", name: plan.name, remaining: 5, usable_sessions: 5, expires_at: "2027-01-01T10:00:00Z" }] : [];
    return new Response(JSON.stringify(value), { headers: { "Content-Type": "application/json" } });
  };
  const root = createRoot(document.getElementById("root")!);
  const input = async (selector: string, value: string) => act(async () => {
    const element = document.querySelector<HTMLInputElement | HTMLSelectElement>(selector)!;
    const prototype = element.tagName === "SELECT" ? dom.window.HTMLSelectElement.prototype : dom.window.HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(prototype, "value")!.set!.call(element, value);
    element.dispatchEvent(new dom.window.Event(element.tagName === "SELECT" ? "change" : "input", { bubbles: true }));
  });
  try {
    await act(async () => root.render(<CommercePanel instituteId="inst" services={[service]} />));
    await input("input[maxlength='120']", plan.name);
    await input("form select", "svc");
    const submit = () => document.querySelector("form")!.dispatchEvent(new dom.window.Event("submit", { bubbles: true, cancelable: true }));
    await act(async () => { submit(); });
    assert.match(document.querySelector("[role='alert']")!.textContent!, /Lost response/);
    await act(async () => { submit(); });
    assert.ok(keys.plan[0]); assert.equal(keys.plan[0], keys.plan[1]);
    assert.match(document.querySelector("[role='status']")!.textContent!, /Forfait configuré/);
    await input("input[type='search']", "Selected");
    await act(async () => { await new Promise(resolve => setTimeout(resolve, 250)); });
    await act(async () => button(customer.display_name).click());
    const selectors = document.querySelectorAll("select");
    await act(async () => { selectors[1].value = "plan"; selectors[1].dispatchEvent(new dom.window.Event("change", { bubbles: true })); });
    await act(async () => button("Attribuer le forfait").click());
    await act(async () => button("Attribuer le forfait").click());
    assert.ok(keys.issue[0]); assert.equal(keys.issue[0], keys.issue[1]);
    assert.match(document.body.textContent!, /5 séances utilisables/);
    assert.equal(button("Attribuer le forfait").disabled, true);
    setAccessToken(`e30.${btoa(JSON.stringify({ role: "accueil" }))}.signature`);
    await act(async () => root.render(<CommercePanel key="operator" instituteId="inst" services={[service]} />));
    assert.equal(document.querySelector("form"), null);
    assert.equal([...document.querySelectorAll("button")].some(item => item.textContent?.includes("Attribuer le forfait")), false);
  } finally { await act(async () => root.unmount()); globalThis.fetch = originalFetch; setAccessToken(null); }
});

for (const covered of [5, 15]) test(`gift checkout recovers one debit across remount and chooses ${covered === 15 ? "full" : "mixed"} closure`, async () => {
  const { CheckoutPanel } = await import("../src/components/CheckoutPanel");
  const originalFetch = globalThis.fetch;
  setAccessToken(`e30.${btoa(JSON.stringify({ role: "responsable_institut", sub: "gift-cashier" }))}.signature`);
  const ticket: QueueTicket = { ...assignmentTicket, status: "ready_for_checkout", currency: "EUR", total_amount: 15, lines: [] };
  const employee = { id: "emp", institute_id: "inst", first_name: "Cashier", status: "available" };
  let applied = false, refreshed = true;
  const attempts: any[] = [], payments: any[] = [];
  const reply = (data: unknown) => new Response(JSON.stringify(data), { headers: { "Content-Type": "application/json" } });
  globalThis.fetch = async (url, init) => {
    assert.equal(String(url).includes("bearer-secret"), false);
    if (String(url).endsWith("/lookup")) return reply({ id: "card", currency: "EUR", remaining: applied ? 25 - covered : 25, usable_amount: applied ? 25 - covered : 25, status: "active" });
    if (init?.method === "POST") {
      attempts.push(JSON.parse(String(init.body))); applied = true;
      if (attempts.length === 1) throw new Error("Lost debit response");
      return reply({ id: "allocation" });
    }
    return reply({ ticket_id: ticket.id, currency: "EUR", total: "15", gift_amount: applied ? covered : 0,
      remaining_due: applied ? 15 - covered : 15, remainder_amount: 0, remainder_method: null,
      allocations: applied ? [{ id: "allocation", card_id: "card", currency: "EUR", amount: covered, reversed_at: null }] : [] });
  };
  const root = createRoot(document.getElementById("root")!);
  const props = { ticket, services: [service], employees: [employee], cashierEmployee: employee, selectedPaymentMethod: "especes" as const,
    onPaymentMethodChange() {}, onAddService() {}, onRemoveLine() {}, onPay(value?: unknown) { payments.push(value); }, onClose() {}, onCancelTicket() {}, async onRefresh() { return refreshed; } };
  const input = (label: string, value: string) => {
    const field = [...document.querySelectorAll("label")].find(item => item.textContent?.startsWith(label))!.querySelector("input")!;
    Object.getOwnPropertyDescriptor(dom.window.HTMLInputElement.prototype, "value")!.set!.call(field, value);
    field.dispatchEvent(new dom.window.Event("input", { bubbles: true }));
  };
  const pay = () => document.querySelector<HTMLButtonElement>(".bm-final-cash-button")!;
  try {
    await act(async () => root.render(<CheckoutPanel {...props} />));
    assert.equal(pay().disabled, false);
    await act(async () => input("Code cadeau", "bearer-secret"));
    await act(async () => button("Rechercher la carte cadeau").click());
    await act(async () => input("Montant cadeau à utiliser", String(covered)));
    refreshed = false;
    await act(async () => button("Utiliser ce crédit cadeau").click());
    assert.equal(attempts.length, 1); assert.equal(pay().disabled, true);
    assert.equal(sessionStorage.getItem("flowpilot.gift-tender:inst:ticket:gift-cashier")!.includes("bearer-secret"), false);
    refreshed = true;
    await act(async () => root.render(<CheckoutPanel key="recover" {...props} />));
    assert.equal(pay().disabled, true);
    await act(async () => button("Actualiser les paiements cadeaux").click());
    assert.equal(pay().disabled, true);
    await act(async () => button("Réessayer ce débit cadeau").click());
    assert.deepEqual(attempts[0], attempts[1]); assert.ok(attempts[0].idempotency_key);
    assert.equal(pay().disabled, false);
    assert.equal(button("Clore en annulation").disabled, true);
    assert.match(document.body.textContent!, /Crédit utilisé/);
    assert.equal(document.body.textContent!.includes("CHF"), false);
    await act(async () => pay().click());
    assert.deepEqual(payments, [covered === 15 ? { payment_method: "carte_cadeau" } : { payment_method: "mixte", remainder_method: "especes" }]);
    assert.equal(sessionStorage.getItem("flowpilot.gift-tender:inst:ticket:gift-cashier"), null);
  } finally { await act(async () => root.unmount()); globalThis.fetch = originalFetch; setAccessToken(null); }
});

test("gift reversal recovery preserves price and freezes payment until the original correction is confirmed", async () => {
  const { CheckoutPanel } = await import("../src/components/CheckoutPanel");
  const originalFetch = globalThis.fetch;
  setAccessToken(`e30.${btoa(JSON.stringify({ role: "responsable_institut", sub: "gift-reverser" }))}.signature`);
  let reversed = false;
  const corrections: any[] = [];
  const ticket: QueueTicket = { ...assignmentTicket, status: "ready_for_checkout", currency: "CHF", total_amount: 15, lines: [] };
  const employee = { id: "emp", institute_id: "inst", first_name: "Cashier", status: "available" };
  globalThis.fetch = async (url, init) => {
    if (init?.method === "POST") {
      corrections.push(JSON.parse(String(init.body))); reversed = true;
      if (corrections.length === 1) throw new Error("Lost reversal response");
      return new Response("{}", { headers: { "Content-Type": "application/json" } });
    }
    return new Response(JSON.stringify({ ticket_id: ticket.id, currency: "CHF", total: 15, gift_amount: reversed ? 0 : 5,
      remaining_due: reversed ? 15 : 10, remainder_amount: 0, remainder_method: null,
      allocations: [{ id: "old-debit", card_id: "card", amount: 5, currency: "CHF", reversed_at: reversed ? "now" : null }] }), { headers: { "Content-Type": "application/json" } });
  };
  const root = createRoot(document.getElementById("root")!);
  const props = { ticket, services: [service], employees: [employee], cashierEmployee: employee, selectedPaymentMethod: "cb" as const,
    onPaymentMethodChange() {}, onAddService() {}, onRemoveLine() {}, onPay() {}, onClose() {}, async onRefresh() { return true; } };
  const pay = () => document.querySelector<HTMLButtonElement>(".bm-final-cash-button")!;
  try {
    await act(async () => root.render(<CheckoutPanel {...props} />));
    await act(async () => [...document.querySelectorAll<HTMLButtonElement>("button")].find(item => item.textContent?.startsWith("Annuler le débit cadeau"))!.click());
    assert.equal(pay().disabled, true); assert.match(document.body.textContent!, /Débit annulé/);
    await act(async () => button("Réessayer cette annulation cadeau").click());
    assert.deepEqual(corrections[0], corrections[1]); assert.equal(corrections.length, 2);
    assert.equal(pay().disabled, false); assert.equal(ticket.total_amount, 15);
    reversed = false;
    setAccessToken(`e30.${btoa(JSON.stringify({ role: "accueil", sub: "gift-reader" }))}.signature`);
    await act(async () => root.render(<CheckoutPanel {...props} />));
    assert.equal([...document.querySelectorAll("button")].some(item => item.textContent?.startsWith("Annuler le débit cadeau")), false);
  } finally { await act(async () => root.unmount()); globalThis.fetch = originalFetch; setAccessToken(null); }
});

test("late gift debit completion cannot refresh or release the writer for another ticket", async () => {
  const { GiftCardWallet } = await import("../src/components/GiftCardWallet");
  const originalFetch = globalThis.fetch;
  setAccessToken(`e30.${btoa(JSON.stringify({ role: "responsable_institut" }))}.signature`);
  const finishes: Record<string, (value: Response) => void> = {};
  const applied: Record<string, boolean> = {};
  const busy: boolean[] = [];
  let refreshes = 0, lease: symbol | null = null;
  const reply = (data: unknown) => new Response(JSON.stringify(data), { headers: { "Content-Type": "application/json" } });
  globalThis.fetch = async (url, init) => {
    const path = new URL(String(url)).pathname;
    if (path.endsWith("/lookup")) {
      const code = JSON.parse(String(init?.body)).code;
      return reply({ id: `card-${code}`, currency: "CHF", remaining: 25, usable_amount: 25, status: "active" });
    }
    if (init?.method === "POST") {
      const id = JSON.parse(String(init.body)).ticket_id; applied[id] = true;
      return new Promise(resolve => { finishes[id] = resolve; });
    }
    const id = path.split("/").at(-2)!;
    return reply({ ticket_id: id, currency: "CHF", total: 15, gift_amount: applied[id] ? 5 : 0,
      remaining_due: applied[id] ? 10 : 15, remainder_amount: 0, remainder_method: null,
      allocations: applied[id] ? [{ id: `debit-${id}`, card_id: `card-${id}`, amount: 5, currency: "CHF", reversed_at: null }] : [] });
  };
  const props = { blocked: false, async onRefresh() { refreshes++; return true; }, onBusy(value: boolean) { busy.push(value); }, onTender() {},
    beginMutation() { if (lease) return null; const stamp = Symbol(); lease = stamp; return () => { if (lease === stamp) lease = null; }; } };
  const root = createRoot(document.getElementById("root")!);
  const render = (id: string) => root.render(<GiftCardWallet {...props} ticket={{ ...assignmentTicket, id, currency: "CHF", status: "ready_for_checkout", total_amount: 15 }} />);
  const input = (label: string, value: string) => {
    const field = [...document.querySelectorAll("label")].find(item => item.textContent?.startsWith(label))!.querySelector("input")!;
    Object.getOwnPropertyDescriptor(dom.window.HTMLInputElement.prototype, "value")!.set!.call(field, value);
    field.dispatchEvent(new dom.window.Event("input", { bubbles: true }));
  };
  try {
    await act(async () => render("old"));
    await act(async () => input("Code cadeau", "old"));
    await act(async () => button("Rechercher la carte cadeau").click());
    await act(async () => input("Montant cadeau à utiliser", "5"));
    await act(async () => button("Utiliser ce crédit cadeau").click());
    assert.ok(finishes.old);
    lease = null; // CheckoutPanel resets writer ownership when its ticket context changes.
    await act(async () => render("new"));
    await act(async () => input("Code cadeau", "new"));
    await act(async () => button("Rechercher la carte cadeau").click());
    await act(async () => input("Montant cadeau à utiliser", "5"));
    await act(async () => button("Utiliser ce crédit cadeau").click());
    assert.ok(finishes.new); refreshes = 0;
    await act(async () => finishes.old(reply({ id: "debit-old" })));
    assert.equal(refreshes, 0); assert.equal(busy.at(-1), true); assert.ok(lease);
    await act(async () => finishes.new(reply({ id: "debit-new" })));
    assert.equal(refreshes, 1); assert.equal(busy.at(-1), false); assert.equal(lease, null);
    assert.equal(document.body.textContent!.includes("old"), false);
  } finally { Object.values(finishes).forEach(finish => finish(reply({}))); await act(async () => root.unmount()); globalThis.fetch = originalFetch; setAccessToken(null); }
});

test("gift recovery refuses a debit payload belonging to a different ticket", async () => {
  const { GiftCardWallet } = await import("../src/components/GiftCardWallet");
  const originalFetch = globalThis.fetch;
  setAccessToken(`e30.${btoa(JSON.stringify({ role: "accueil", sub: "scoped-reader" }))}.signature`);
  const key = "flowpilot.gift-tender:inst:ticket:scoped-reader";
  sessionStorage.setItem(key, JSON.stringify({ path: "/gift-cards/institutes/inst/card/allocations", label: "Recover",
    payload: { ticket_id: "another-ticket", amount: "5", idempotency_key: "foreign-intent" } }));
  let writes = 0;
  globalThis.fetch = async (url, init) => { if (init?.method === "POST") writes++; return emptyGiftTender(assignmentTicket); };
  const root = createRoot(document.getElementById("root")!);
  try {
    await act(async () => root.render(<GiftCardWallet ticket={assignmentTicket} blocked={false} onBusy={() => {}} onTender={() => {}} onRefresh={async () => true} beginMutation={() => () => {}} />));
    assert.match(document.body.textContent!, /incompatible avec ce ticket/);
    assert.equal([...document.querySelectorAll("button")].some(item => item.textContent?.includes("Réessayer ce débit")), false);
    await act(async () => button("Actualiser les paiements cadeaux").click());
    assert.equal(writes, 0);
    sessionStorage.setItem(key, JSON.stringify({ path: "/gift-cards/institutes/inst/allocations/foreign-debit/reverse",
      payload: { reason: "Stored correction" }, label: "Recover reversal" }));
    setAccessToken(`e30.${btoa(JSON.stringify({ role: "responsable_institut", sub: "scoped-reader" }))}.signature`);
    await act(async () => root.render(<GiftCardWallet ticket={assignmentTicket} blocked={false} onBusy={() => {}} onTender={() => {}} onRefresh={async () => true} beginMutation={() => () => {}} />));
    await act(async () => button("Réessayer cette annulation cadeau").click());
    assert.match(document.body.textContent!, /historique du ticket/);
    assert.equal(writes, 0);
  } finally { sessionStorage.removeItem(key); await act(async () => root.unmount()); globalThis.fetch = originalFetch; setAccessToken(null); }
});

test("gift tender read failures keep payment unavailable until server facts are verified", async () => {
  const { CheckoutPanel } = await import("../src/components/CheckoutPanel");
  const originalFetch = globalThis.fetch;
  let readsWork = false;
  const ticket: QueueTicket = { ...assignmentTicket, currency: "EUR", status: "ready_for_checkout", total_amount: 15 };
  globalThis.fetch = async () => { if (!readsWork) throw new Error("Tender read unavailable"); return emptyGiftTender(ticket); };
  const root = createRoot(document.getElementById("root")!);
  const employee = { id: "emp", institute_id: "inst", first_name: "Cashier", status: "available" };
  try {
    await act(async () => root.render(<CheckoutPanel ticket={ticket} services={[service]} employees={[employee]} cashierEmployee={employee}
      selectedPaymentMethod="cb" onPaymentMethodChange={() => {}} onAddService={() => {}} onRemoveLine={() => {}} onPay={() => {}} onClose={() => {}} onRefresh={async () => true} />));
    assert.equal(document.querySelector<HTMLButtonElement>(".bm-final-cash-button")!.disabled, true);
    readsWork = true;
    await act(async () => button("Actualiser les paiements cadeaux").click());
    assert.equal(document.querySelector<HTMLButtonElement>(".bm-final-cash-button")!.disabled, false);
  } finally { await act(async () => root.unmount()); globalThis.fetch = originalFetch; }
});

test("checkout currency confirmation keeps payment locked until operational refresh succeeds", async () => {
  const { CheckoutPanel } = await import("../src/components/CheckoutPanel");
  const originalFetch = globalThis.fetch;
  const ticket: QueueTicket = { ...assignmentTicket, status: "ready_for_checkout", currency: null, total_amount: 15, lines: [] };
  let refreshSucceeds = false, confirmations = 0;
  globalThis.fetch = async (url, init) => {
    if (init?.method === "PATCH") { confirmations++; assert.deepEqual(JSON.parse(String(init.body)), { currency: "EUR", reason: "Quote confirmation" }); throw new Error("Lost confirmation response"); }
    if (String(url).endsWith("/tenders")) return emptyGiftTender(ticket);
    return new Response(JSON.stringify({ currency: "EUR" }), { headers: { "Content-Type": "application/json" } });
  };
  const employee = { id: "emp", institute_id: "inst", first_name: "Test", status: "available" };
  const props = { ticket, services: [service], employees: [employee], cashierEmployee: employee, selectedPaymentMethod: "cb" as const,
    onPaymentMethodChange() {}, onAddService() {}, onRemoveLine() {}, onPay() {}, onClose() {},
    async onRefresh() { return refreshSucceeds; } };
  const root = createRoot(document.getElementById("root")!);
  const pay = () => document.querySelector<HTMLButtonElement>(".bm-final-cash-button")!;
  try {
    await act(async () => root.render(<CheckoutPanel {...props} />));
    assert.equal(pay().disabled, false);
    await act(async () => {
      const input = document.querySelector<HTMLInputElement>("section[aria-label='Devise du ticket'] input")!;
      Object.getOwnPropertyDescriptor(dom.window.HTMLInputElement.prototype, "value")!.set!.call(input, "Quote confirmation");
      input.dispatchEvent(new dom.window.Event("input", { bubbles: true }));
    });
    await act(async () => button("Confirmer la devise EUR").click());
    assert.equal(confirmations, 1); assert.equal(pay().disabled, true);
    await act(async () => button("Actualiser la devise du ticket").click());
    assert.equal(pay().disabled, true);
    refreshSucceeds = true;
    await act(async () => root.render(<CheckoutPanel {...props} ticket={{ ...ticket, currency: "EUR" }} />));
    assert.equal(pay().disabled, true);
    await act(async () => button("Actualiser la devise du ticket").click());
    assert.equal(confirmations, 1); assert.equal(pay().disabled, false);
    assert.equal(document.querySelector("section[aria-label='Devise du ticket']"), null);
  } finally { await act(async () => root.unmount()); globalThis.fetch = originalFetch; }
});

test("disposed currency confirmation cannot refresh or unlock another ticket", async () => {
  const { CheckoutCurrency } = await import("../src/components/CheckoutCurrency");
  const originalFetch = globalThis.fetch;
  let finish!: (value: Response) => void, refreshes = 0;
  const busy: boolean[] = [];
  globalThis.fetch = async (url, init) => init?.method === "PATCH" ? new Promise(resolve => { finish = resolve; })
    : new Response(JSON.stringify({ currency: "CHF" }), { headers: { "Content-Type": "application/json" } });
  const root = createRoot(document.getElementById("root")!);
  const props = { blocked: false, async onRefresh() { refreshes++; return true; }, onBusy(value: boolean) { busy.push(value); }, beginMutation() { return () => {}; } };
  const ticket = { ...assignmentTicket, status: "ready_for_checkout", currency: null };
  try {
    await act(async () => root.render(<CheckoutCurrency {...props} ticket={ticket} />));
    await act(async () => {
      const input = document.querySelector("input")!;
      Object.getOwnPropertyDescriptor(dom.window.HTMLInputElement.prototype, "value")!.set!.call(input, "Confirmed quote");
      input.dispatchEvent(new dom.window.Event("input", { bubbles: true }));
    });
    await act(async () => button("Confirmer la devise CHF").click());
    await act(async () => root.render(<CheckoutCurrency {...props} ticket={{ ...ticket, id: "another", currency: "EUR" }} />));
    await act(async () => finish(new Response(JSON.stringify({ currency: "CHF" }), { headers: { "Content-Type": "application/json" } })));
    assert.equal(refreshes, 0); assert.deepEqual(busy, [true]);
    assert.equal(document.querySelector("section"), null);
  } finally { await act(async () => root.unmount()); globalThis.fetch = originalFetch; }
});

test("gift management configures explicit currency and recovers one issuance after a lost response", async () => {
  const { GiftCardManagement } = await import("../src/components/GiftCardManagement");
  const originalFetch = globalThis.fetch;
  setAccessToken(`e30.${btoa(JSON.stringify({ role: "responsable_institut", sub: "gift-manager" }))}.signature`);
  let currency: string | undefined;
  const intents: any[] = [];
  const reply = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { "Content-Type": "application/json" } });
  globalThis.fetch = async (url, init) => {
    if (init?.method === "PUT") { currency = JSON.parse(String(init.body)).currency; return reply({ currency }); }
    if (init?.method === "POST") {
      intents.push(JSON.parse(String(init.body)));
      if (intents.length === 1) throw new Error("Lost issuance response");
      return reply({ id: "gift", code: "secret-issued-code", initial_amount: "25.10", currency,
        expires_at: "2027-10-05T10:00:00" });
    }
    return currency ? reply({ currency }) : reply({ detail: "Configurer la devise des cartes cadeaux pour cet institut" }, 400);
  };
  const root = createRoot(document.getElementById("root")!);
  const input = (index: number, value: string) => {
    const field = document.querySelectorAll("input")[index];
    Object.getOwnPropertyDescriptor(dom.window.HTMLInputElement.prototype, "value")!.set!.call(field, value);
    field.dispatchEvent(new dom.window.Event("input", { bubbles: true }));
  };
  try {
    await act(async () => root.render(<GiftCardManagement instituteId="inst" />));
    assert.equal(document.querySelector<HTMLSelectElement>("select")!.value, "");
    assert.equal(button("Émettre la carte cadeau").disabled, true);
    await act(async () => { const select = document.querySelector("select")!; select.value = "EUR"; select.dispatchEvent(new dom.window.Event("change", { bubbles: true })); });
    await act(async () => button("Enregistrer la devise").click());
    assert.equal(currency, "EUR"); assert.match(document.body.textContent!, /Devise configurée : EUR/);
    await act(async () => { input(0, "25,10"); input(2, "Attribution commerciale"); });
    await act(async () => button("Émettre la carte cadeau").click());
    assert.equal(intents.length, 1);
    assert.equal(intents[0].amount, "25.10");
    assert.equal(document.querySelector("input")!.closest("fieldset")!.disabled, true);
    assert.equal(document.querySelector("textarea"), null);
    assert.equal(JSON.parse(sessionStorage.getItem("flowpilot.gift-issue:inst:gift-manager")!).idempotency_key, intents[0].idempotency_key);
    await act(async () => root.render(<GiftCardManagement key="recover-remount" instituteId="inst" />));
    await act(async () => button("Récupérer cette émission").click());
    assert.equal(intents.length, 2); assert.deepEqual(intents[0], intents[1]);
    assert.ok(intents[0].idempotency_key);
    assert.equal(document.querySelector<HTMLTextAreaElement>("textarea")!.value, "secret-issued-code");
    assert.match(document.body.textContent!, /25.10 EUR/);
    assert.equal(button("Émettre la carte cadeau").disabled, true);
    await act(async () => button("Nouvelle carte cadeau").click());
    assert.equal(document.querySelector("textarea"), null);
    setAccessToken(`e30.${btoa(JSON.stringify({ role: "accueil" }))}.signature`);
    await act(async () => root.render(<GiftCardManagement key="reception" instituteId="inst" />));
    assert.equal(document.querySelector("form"), null);
    assert.match(document.body.textContent!, /réservées à la responsable/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = originalFetch; setAccessToken(null); }
});

test("gift issuance cannot expose an old institute code after a context switch", async () => {
  const { GiftCardManagement } = await import("../src/components/GiftCardManagement");
  const originalFetch = globalThis.fetch;
  setAccessToken(`e30.${btoa(JSON.stringify({ role: "responsable_institut", sub: "gift-manager" }))}.signature`);
  let finish!: (value: Response) => void;
  const intents: any[] = [];
  globalThis.fetch = async (url, init) => init?.method === "POST" ? new Promise(resolve => { intents.push(JSON.parse(String(init.body))); finish = resolve; })
    : new Response(JSON.stringify({ currency: String(url).includes("/new/") ? "EUR" : "CHF" }), { headers: { "Content-Type": "application/json" } });
  const root = createRoot(document.getElementById("root")!);
  try {
    await act(async () => root.render(<GiftCardManagement instituteId="old" />));
    await act(async () => {
      for (const [index, value] of [[0, "10"], [2, "Commercial grant"]] as const) {
        const field = document.querySelectorAll("input")[index];
        Object.getOwnPropertyDescriptor(dom.window.HTMLInputElement.prototype, "value")!.set!.call(field, value);
        field.dispatchEvent(new dom.window.Event("input", { bubbles: true }));
      }
    });
    await act(async () => button("Émettre la carte cadeau").click());
    await act(async () => root.render(<GiftCardManagement instituteId="new" />));
    await act(async () => finish(new Response(JSON.stringify({ id: "old", code: "old-secret", initial_amount: "10", currency: "CHF", expires_at: "2027-10-05T10:00:00Z" }), { headers: { "Content-Type": "application/json" } })));
    assert.match(document.body.textContent!, /Devise configurée : EUR/);
    assert.equal(document.querySelector("textarea"), null);
    assert.equal(document.querySelector("input")!.value, "");
    await act(async () => root.render(<GiftCardManagement instituteId="old" />));
    await act(async () => button("Récupérer cette émission").click());
    assert.deepEqual(intents[0], intents[1]);
    await act(async () => finish(new Response(JSON.stringify({ id: "old", code: "old-secret", initial_amount: "10", currency: "CHF", expires_at: "2027-10-05T10:00:00Z" }), { headers: { "Content-Type": "application/json" } })));
    assert.equal(document.querySelector<HTMLTextAreaElement>("textarea")!.value, "old-secret");
    assert.equal(sessionStorage.getItem("flowpilot.gift-issue:old:gift-manager")!.includes("old-secret"), false);
    await act(async () => button("Nouvelle carte cadeau").click());
  } finally { await act(async () => root.unmount()); globalThis.fetch = originalFetch; setAccessToken(null); }
});

test("membership management retries configuration, issue and renewal without changing their replay keys", async () => {
  const { MembershipManagement } = await import("../src/components/MembershipManagement");
  const originalFetch = globalThis.fetch;
  setAccessToken(`e30.${btoa(JSON.stringify({ role: "responsable_institut" }))}.signature`);
  const customer = { id: "customer_member", institute_id: "inst", display_name: "Member client", phone: null, created_at: "2026-10-05T10:00:00Z" };
  const plan = { id: "member-plan", name: "Monthly rights", valid_days: 30 };
  const keys: Record<string, string[]> = { plan: [], issue: [], renew: [] };
  let created = false; let issued = false; let renewed = false;
  globalThis.fetch = async (url, init) => {
    const path = new URL(String(url)).pathname;
    if (init?.method === "POST") {
      const payload = JSON.parse(String(init.body));
      const kind = path.endsWith("/plans") ? "plan" : path.endsWith("/renew") ? "renew" : "issue";
      keys[kind].push(payload.idempotency_key);
      if (kind === "plan") { created = true; assert.equal(payload.valid_days, 30); }
      else if (kind === "issue") { issued = true; assert.equal(payload.customer_id, customer.id); }
      else renewed = true;
      if (keys[kind].length === 1) throw new Error("Lost membership response");
      return new Response(JSON.stringify({ id: kind }), { headers: { "Content-Type": "application/json" } });
    }
    const data = path.endsWith("/plans") ? created ? [plan] : [] : path.endsWith("/history")
      ? renewed ? [{ id: "renewal", occurred_at: "2026-10-05T11:00:00Z", active_until: "2026-12-04T10:00:00Z" }] : []
      : issued ? [{ id: "member", name: plan.name, status: "active", active_from: "2026-10-05T10:00:00Z", active_until: renewed ? "2026-12-04T10:00:00Z" : "2026-11-04T10:00:00Z" }] : [];
    return new Response(JSON.stringify(data), { headers: { "Content-Type": "application/json" } });
  };
  const root = createRoot(document.getElementById("root")!);
  const busy: boolean[] = [];
  try {
    await act(async () => root.render(<MembershipManagement instituteId="inst" customer={customer} disabled={false} onBusy={value => busy.push(value)} />));
    await act(async () => {
      const input = document.querySelector<HTMLInputElement>("input[maxlength='120']")!;
      Object.getOwnPropertyDescriptor(dom.window.HTMLInputElement.prototype, "value")!.set!.call(input, plan.name);
      input.dispatchEvent(new dom.window.Event("input", { bubbles: true }));
    });
    const submit = () => document.querySelector("form")!.dispatchEvent(new dom.window.Event("submit", { bubbles: true, cancelable: true }));
    await act(async () => { submit(); });
    await act(async () => { submit(); });
    assert.ok(keys.plan[0]); assert.equal(keys.plan[0], keys.plan[1]);
    await act(async () => {
      const select = document.querySelector<HTMLSelectElement>("select")!;
      select.value = plan.id; select.dispatchEvent(new dom.window.Event("change", { bubbles: true }));
    });
    await act(async () => button("Attribuer l’abonnement").click());
    await act(async () => button("Attribuer l’abonnement").click());
    assert.ok(keys.issue[0]); assert.equal(keys.issue[0], keys.issue[1]);
    assert.equal(button("Attribuer l’abonnement").disabled, true);
    await act(async () => button("Renouveler Monthly rights").click());
    await act(async () => button("Renouveler Monthly rights").click());
    assert.ok(keys.renew[0]); assert.equal(keys.renew[0], keys.renew[1]);
    assert.match(document.body.textContent!, /Historique des renouvellements/);
    assert.match(document.body.textContent!, /04\/12\/2026/);
    assert.deepEqual(busy, [true, false, true, false, true, false, true, false, true, false, true, false]);
    setAccessToken(`e30.${btoa(JSON.stringify({ role: "accueil" }))}.signature`);
    await act(async () => root.render(<MembershipManagement key="reception" instituteId="inst" customer={customer} disabled={false} onBusy={() => {}} />));
    assert.equal(document.querySelector("form"), null);
    assert.equal([...document.querySelectorAll("button")].some(item => item.textContent?.includes("Renouveler")), false);
    assert.match(document.body.textContent!, /Monthly rights/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = originalFetch; setAccessToken(null); }
});

test("member checkout serializes wallets, recovers lost pricing and retains historical line protections", async () => {
  const { CheckoutPanel } = await import("../src/components/CheckoutPanel");
  const originalFetch = globalThis.fetch;
  setAccessToken(`e30.${btoa(JSON.stringify({ role: "responsable_institut" }))}.signature`);
  let applied = false; let reversed = false; let reconciles = false;
  let posts = 0; let resolvePost!: () => void;
  const waiting = new Promise<void>(resolve => { resolvePost = resolve; });
  const ticket: QueueTicket = { ...assignmentTicket, status: "ready_for_checkout", customer_id: "customer_member", total_amount: 20,
    lines: [{ id: "member-line", ticket_id: "ticket", service_id: "svc", quantity: 1, duration_minutes: 10,
      unit_price: 15, total: 15, revenue_category: "care", performed_by_employee_id: "emp", status: "completed" },
      { id: "uncovered-line", ticket_id: "ticket", service_id: "unquoted", quantity: 1, duration_minutes: 10,
        unit_price: 5, total: 5, revenue_category: "care", performed_by_employee_id: "emp", status: "completed" }] };
  globalThis.fetch = async (url, init) => {
    const path = new URL(String(url)).pathname;
    if (init?.method === "POST") {
      posts++; assert.ok(path.includes("/memberships/"));
      if (path.endsWith("/reverse")) reversed = true;
      else { applied = true; await waiting; throw new Error("Lost member price response"); }
      return new Response("{}", { headers: { "Content-Type": "application/json" } });
    }
    if (path.endsWith("/tenders")) return emptyGiftTender(ticket);
    const data = path.includes("/customers/") ? { id: "customer_member", display_name: "Member client", phone: null }
      : path.includes("/memberships/") ? path.endsWith("/benefits") ? applied ? [{ id: "benefit", ticket_line_id: "member-line", reversed_at: reversed ? "now" : null }] : []
      : [{ id: "member", name: "Monthly rights", status: "active", active_until: "2027-01-01T10:00:00Z" }]
      : path.endsWith("/history") ? [] : [{ id: "package", name: "Cure", service_id: "svc", remaining: 2, usable_sessions: 2, status: "active", expires_at: "2027-01-01T10:00:00Z" }];
    return new Response(JSON.stringify(data), { headers: { "Content-Type": "application/json" } });
  };
  const root = createRoot(document.getElementById("root")!);
  const employee = { id: "emp", institute_id: "inst", first_name: "Cashier", skills: [], status: "available" };
  const render = () => root.render(<CheckoutPanel ticket={ticket} services={[{ ...service, price_member: 9.9 }]} employees={[employee]} cashierEmployee={employee}
    selectedPaymentMethod="cb" onPaymentMethodChange={() => {}} onAddService={() => {}} onRemoveLine={() => {}}
    onPay={() => {}} onClose={() => {}} onCancelTicket={() => {}} onRefresh={async () => {
      if (!reconciles) return false;
      const memberLinePrice = applied && !reversed ? 9.9 : 15;
      ticket.total_amount = memberLinePrice + 5;
      ticket.lines![0].unit_price = memberLinePrice; ticket.lines![0].total = memberLinePrice;
      render(); return true;
    }} />);
  try {
    await act(async () => render());
    const cureButton = button("Utiliser 1 séance");
    await act(async () => { button("Appliquer le tarif membre").click(); cureButton.click(); });
    assert.equal(posts, 1);
    assert.equal(document.querySelector<HTMLButtonElement>(".bm-final-cash-button")!.disabled, true);
    await act(async () => { resolvePost(); });
    assert.equal(document.querySelector<HTMLButtonElement>(".bm-final-cash-button")!.disabled, true);
    assert.equal(button("Clore en annulation").disabled, true);
    assert.equal([...document.querySelectorAll("button")].some(item => item.textContent?.includes("Utiliser 1 séance")), false);
    reconciles = true;
    await act(async () => button("Actualiser les abonnements en caisse").click());
    assert.equal(document.querySelector<HTMLButtonElement>(".bm-final-cash-button")!.disabled, false);
    await act(async () => button("Annuler le tarif membre").click());
    assert.equal(posts, 2); assert.equal(ticket.total_amount, 20);
    assert.ok(button("Utiliser 1 séance"));
    assert.equal(button("Clore en annulation").disabled, false);
    const removeButtons = document.querySelectorAll<HTMLButtonElement>(".bm-cash-trash");
    assert.equal(removeButtons[0].disabled, true);
    assert.equal(removeButtons[1].disabled, false);
  } finally { resolvePost(); await act(async () => root.unmount()); globalThis.fetch = originalFetch; setAccessToken(null); }
});

test("a disposed membership write cannot refresh or unlock a newly selected checkout", async () => {
  const { CheckoutPanel } = await import("../src/components/CheckoutPanel");
  const originalFetch = globalThis.fetch;
  setAccessToken(`e30.${btoa(JSON.stringify({ role: "responsable_institut" }))}.signature`);
  const releases: Record<string, () => void> = {};
  let newApplied = false; let refreshes = 0;
  const makeTicket = (id: string): QueueTicket => ({ ...assignmentTicket, id, customer_id: id, status: "ready_for_checkout", total_amount: 15,
    lines: [{ id: `${id}-line`, ticket_id: id, service_id: "svc", quantity: 1, duration_minutes: 10,
      unit_price: 15, total: 15, revenue_category: "care", performed_by_employee_id: "emp", status: "completed" }] });
  let shown = makeTicket("old");
  globalThis.fetch = async (url, init) => {
    const address = new URL(String(url));
    const path = address.pathname;
    if (path.endsWith("/tenders")) return emptyGiftTender(shown);
    if (init?.method === "POST") {
      const id = path.includes("/old/") ? "old" : "new";
      if (id === "new") newApplied = true;
      await new Promise<void>(resolve => { releases[id] = resolve; });
      return new Response("{}", { headers: { "Content-Type": "application/json" } });
    }
    const value = path.includes("/customers/") ? { id: shown.customer_id, display_name: "Client" }
      : path.includes("/memberships/") ? path.endsWith("/benefits") ? newApplied && path.includes("/new/")
        ? [{ id: "new-benefit", ticket_line_id: "new-line", reversed_at: null }] : []
        : [{ id: address.searchParams.get("customer_id"), name: "Member", status: "active", active_until: "2027-01-01T10:00:00Z" }]
      : [];
    return new Response(JSON.stringify(value), { headers: { "Content-Type": "application/json" } });
  };
  const root = createRoot(document.getElementById("root")!);
  const employee = { id: "emp", institute_id: "inst", first_name: "Cashier", skills: [], status: "available" };
  const render = () => root.render(<CheckoutPanel ticket={shown} services={[{ ...service, price_member: 9.9 }]} employees={[employee]} cashierEmployee={employee}
    selectedPaymentMethod="cb" onPaymentMethodChange={() => {}} onAddService={() => {}} onRemoveLine={() => {}}
    onPay={() => {}} onClose={() => {}} onRefresh={async () => {
      refreshes++; shown.total_amount = 9.9; shown.lines![0].total = 9.9; shown.lines![0].unit_price = 9.9; render(); return true;
    }} />);
  try {
    await act(async () => render());
    await act(async () => button("Appliquer le tarif membre").click());
    assert.ok(releases.old);
    shown = makeTicket("new");
    await act(async () => render());
    await act(async () => button("Appliquer le tarif membre").click());
    assert.ok(releases.new);
    await act(async () => releases.old());
    assert.equal(refreshes, 0);
    assert.equal(document.querySelector<HTMLButtonElement>(".bm-final-cash-button")!.disabled, true);
    await act(async () => releases.new());
    assert.equal(refreshes, 1);
    assert.equal(document.querySelector<HTMLButtonElement>(".bm-final-cash-button")!.disabled, false);
  } finally { Object.values(releases).forEach(release => release()); await act(async () => root.unmount()); globalThis.fetch = originalFetch; setAccessToken(null); }
});

for (const kind of ["package", "membership"] as const) {
  test(`${kind} wallet discards a delayed read from a disposed StrictMode lifecycle`, async () => {
    const { PackageWallet } = await import("../src/components/PackageWallet");
    const { MembershipWallet } = await import("../src/components/MembershipWallet");
    const originalFetch = globalThis.fetch;
    setAccessToken("wallet-read-operator");
    let release!: (response: Response) => void;
    const first = new Promise<Response>(resolve => { release = resolve; });
    let lists = 0; let histories = 0;
    globalThis.fetch = async url => {
      const path = new URL(String(url)).pathname;
      if (path.includes("/customers/")) return new Response(JSON.stringify({ id: "customer_read", display_name: "Read client" }), { headers: { "Content-Type": "application/json" } });
      if (path.endsWith("/history") || path.endsWith("/benefits")) histories++;
      else if (++lists === 1) return first;
      return new Response("[]", { headers: { "Content-Type": "application/json" } });
    };
    const root = createRoot(document.getElementById("root")!);
    const ticket = { ...assignmentTicket, customer_id: "customer_read", status: "ready_for_checkout" };
    const callbacks = { onRefresh: async () => true, onBusy() {}, onCoverage() {} };
    try {
      await act(async () => root.render(<React.StrictMode>{kind === "package"
        ? <PackageWallet ticket={ticket} {...callbacks} onCustomer={() => {}} />
        : <MembershipWallet ticket={ticket} services={[service]} blocked={false} excludedLines={[]} beginMutation={() => () => {}} {...callbacks} />}</React.StrictMode>));
      assert.equal(lists, 2);
      await act(async () => release(new Response(JSON.stringify([{ id: "obsolete", name: "Obsolete wallet read", status: "active",
        service_id: "svc", remaining: 1, usable_sessions: 1, expires_at: "2027-01-01T10:00:00Z", active_until: "2027-01-01T10:00:00Z" }]),
        { headers: { "Content-Type": "application/json" } })));
      assert.equal(histories, 0);
      assert.equal(document.body.textContent!.includes("Obsolete wallet read"), false);
    } finally { release(new Response("[]")); await act(async () => root.unmount()); globalThis.fetch = originalFetch; setAccessToken(null); }
  });
}

function button(text: string) {
  const element = [...document.querySelectorAll("button")].find((item) => item.textContent?.includes(text));
  assert.ok(element, `Missing button: ${text}`);
  return element;
}

test("anonymous arrival needs service selection and one submit; failed submission remains retryable", async () => {
  const root = createRoot(document.getElementById("root")!);
  let attempts = 0;
  let closed = false;
  const submitted: unknown[] = [];
  await act(async () => root.render(<NewTicketWorkflow open categories={[category]} services={[service]}
    onClose={() => { closed = true; }} onValidate={async (payload) => {
      submitted.push(payload);
      if (++attempts === 1) throw new Error("Temporary network failure");
    }} />));
  assert.equal(document.querySelector("input[placeholder='Nom']"), null);
  assert.equal(button("Ajouter à la file").disabled, true);
  await act(async () => button("Aisselles").click());
  assert.equal(button("Ajouter à la file").disabled, false);
  await act(async () => button("Ajouter à la file").click());
  assert.equal(closed, false);
  assert.ok(document.querySelector("[role='dialog']"));
  await act(async () => button("Ajouter à la file").click());
  assert.equal(closed, true);
  assert.deepEqual(submitted[0], submitted[1]);
  assert.deepEqual((submitted[0] as { customer: unknown }).customer, {
    lastName: "", firstName: "", phone: "", identificationMode: "passage_bm",
  });
  await act(async () => root.unmount());
});

test("HTTP integration carries the operator token and displays standardized business errors", async () => {
  const originalFetch = globalThis.fetch;
  const requests: Array<{ path: string; token: string | null }> = [];
  setAccessToken("operator-test-token");
  globalThis.fetch = async (url, init) => {
    requests.push({ path: String(url), token: new Headers(init?.headers).get("Authorization") });
    if (String(url).endsWith("/tickets")) return new Response(JSON.stringify({ error: {
      code: "http_400", message: "La collaboratrice a deja un ticket affecte",
    } }), { status: 400, headers: { "Content-Type": "application/json" } });
    return new Response("[]", { headers: { "Content-Type": "application/json" } });
  };
  try {
    await apiGet("/tickets/waiting?institute_id=demo");
    assert.equal(requests[0].token, "Bearer operator-test-token");
    await assert.rejects(apiPost("/tickets", {}), /La collaboratrice a deja un ticket affecte/);
    await apiPost("/auth/login", { email: "test@example.com", password: "test" });
    assert.equal(requests[2].token, null);
  } finally {
    setAccessToken(null);
    globalThis.fetch = originalFetch;
  }
});

test("operator login opens the app and logout clears the session", async () => {
  const { SessionGate } = await import("../src/components/SessionGate");
  const originalFetch = globalThis.fetch;
  let credentials: unknown;
  globalThis.fetch = async (url, init) => {
    if (String(url).endsWith("/auth/login")) {
      credentials = JSON.parse(String(init?.body));
      return new Response(JSON.stringify({ access_token: "operator-session", role: "accueil" }), {
        headers: { "Content-Type": "application/json" },
      });
    }
    return new Response("[]", { headers: { "Content-Type": "application/json" } });
  };
  const root = createRoot(document.getElementById("root")!);
  try {
    await act(async () => root.render(<SessionGate />));
    const setInput = (id: string, value: string) => {
      const input = document.getElementById(id)!;
      Object.getOwnPropertyDescriptor(dom.window.HTMLInputElement.prototype, "value")!.set!.call(input, value);
      input.dispatchEvent(new dom.window.Event("input", { bubbles: true }));
    };
    await act(async () => {
      setInput("flow-email", "operator@example.com");
      setInput("flow-password", "shift-password");
    });
    await act(async () => document.querySelector("form")!.dispatchEvent(new dom.window.Event("submit", { bubbles: true, cancelable: true })));
    assert.deepEqual(credentials, { email: "operator@example.com", password: "shift-password" });
    assert.equal(sessionStorage.getItem("flowpilot.access_token"), "operator-session");
    assert.ok(button("Déconnexion"));
    await act(async () => button("Déconnexion").click());
    assert.equal(sessionStorage.getItem("flowpilot.access_token"), null);
    assert.ok(document.getElementById("flow-email"));
  } finally {
    await act(async () => root.unmount());
    globalThis.fetch = originalFetch;
    setAccessToken(null);
  }
});


test("loyalty overview rejects late old-customer facts and hides stale balances after failed refresh", async () => {
  const { LoyaltyOverview } = await import("../src/components/LoyaltyOverview");
  const root = createRoot(document.getElementById("root")!);
  const original = globalThis.fetch;
  const waiting: Array<(response: Response) => void> = [];
  let fail = false;
  const json = (value: unknown) => new Response(JSON.stringify(value), { headers: { "Content-Type": "application/json" } });
  globalThis.fetch = async input => {
    const path = String(input);
    if (path.includes("/customers/old")) return await new Promise<Response>(resolve => waiting.push(resolve));
    if (fail) return new Response(JSON.stringify({ detail: "Ledger unavailable" }), { status: 503, headers: { "Content-Type": "application/json" } });
    assert.ok(path.endsWith("/snapshot"));
    return json({ balance: { customer_id: "new", points: 7, tier: null },
      entries: [{ id: "entry", points: 7, reason: "Correction explicite", occurred_at: "2026-10-06T10:00:00Z" }],
      redemptions: [{ id: "use", points_cost: 10, quantity: 1, occurred_at: "2026-10-06T10:00:00Z", reversed_at: "2026-10-06T11:00:00Z", reversal_reason: "Correction" }] });
  };
  try {
    await act(async () => root.render(<LoyaltyOverview instituteId="inst" customer={{ id: "old", display_name: "Old" } as any} />));
    await act(async () => root.render(<LoyaltyOverview instituteId="inst" customer={{ id: "new", display_name: "New" } as any} />));
    assert.match(document.body.textContent!, /7 points/);
    assert.match(document.body.textContent!, /Annulee : Correction/);
    await act(async () => waiting.forEach((resolve, index) => resolve(json({ balance: { customer_id: "old", points: 999, tier: null }, entries: [], redemptions: [] }))));
    assert.doesNotMatch(document.body.textContent!, /999 points/);
    fail = true;
    await act(async () => [...document.querySelectorAll<HTMLButtonElement>("button")].find(row => row.textContent === "Actualiser la fidelite")!.click());
    assert.match(document.querySelector("[role='alert']")!.textContent!, /Ledger unavailable/);
    assert.doesNotMatch(document.body.textContent!, /7 points/);
    await act(async () => root.render(<LoyaltyOverview instituteId="other" />));
    assert.match(document.body.textContent!, /Selectionnez une cliente/);
    assert.equal(document.querySelector("[role='alert']"), null);
  } finally { globalThis.fetch = original; await act(async () => root.unmount()); }
});
