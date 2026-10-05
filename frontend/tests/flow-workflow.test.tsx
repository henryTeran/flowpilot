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

test("selecting a ticket and starting uses the feasible employee in two actions", async () => {
  const { default: App } = await import("../src/App");
  const originalFetch = globalThis.fetch;
  const originalWebSocket = globalThis.WebSocket;
  const writes: Array<{ path: string; body: Record<string, string> }> = [];
  const selected = { ...assignmentTicket, lines: [{ id: "line", ticket_id: "ticket", service_id: "svc",
    quantity: 1, duration_minutes: 45, unit_price: 15, total: 15, revenue_category: "care", status: "pending" }] };
  let started = false;
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
    } else if (path === "/institutes") payload = [{ id: "inst", name: "Test", city: "Test", timezone: "Europe/Berlin", status: "active" }];
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
    assert.deepEqual(writes.map((request) => request.path), ["/tickets/ticket/assign", "/planning/sessions/start"]);
    assert.equal(writes[0].body.employee_id, "emp");
    assert.equal(writes[1].body.employee_id, "emp");
  } finally {
    await act(async () => root.unmount());
    globalThis.fetch = originalFetch;
    globalThis.WebSocket = originalWebSocket;
  }
});

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
