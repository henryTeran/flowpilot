import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import React, { act } from "react";
import { SkillMatrixPanel } from "../src/components/SkillMatrixPanel";
import { validSkillMatrix, type SkillMatrix } from "../src/workforce-utils";
import { setAccessToken } from "../src/api/session";

const dom = new JSDOM("<!doctype html><div id='root'></div>", { url: "http://localhost:5173" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (role = "responsable_institut", sub = "manager") => `h.${Buffer.from(JSON.stringify({ role, sub })).toString("base64url")}.s`;
const response = (value: unknown) => new Response(JSON.stringify(value), { headers: { "Content-Type": "application/json" } });
function button(text: string) { return [...document.querySelectorAll<HTMLButtonElement>("button")].find(item => item.textContent === text)!; }
function matrix(institute = "inst", employeeOffset = 0, serviceOffset = 0, employeeTotal = 12, serviceTotal = 7): SkillMatrix {
  const employees = Array.from({ length: Math.min(10, Math.max(0, employeeTotal - employeeOffset)) }, (_, i) => ({
    id: `emp-${i + employeeOffset}`, first_name: `Employee ${i + employeeOffset}`, status: "absent", skills: i % 2 ? [] : ["SPECIAL"],
  }));
  const services = Array.from({ length: Math.min(5, Math.max(0, serviceTotal - serviceOffset)) }, (_, i) => ({
    id: `svc-${i + serviceOffset}`, name: `Service ${i + serviceOffset}`, required_skills: i % 2 ? [] : ["SPECIAL"],
    requirement_state: i % 2 ? "none_recorded" as const : "recorded" as const,
  }));
  return { institute_id: institute, generated_at: "2026-10-07T22:30:00Z",
    employee_page: { offset: employeeOffset, limit: 10, total: employeeTotal }, service_page: { offset: serviceOffset, limit: 5, total: serviceTotal },
    employees, services, cells: employees.flatMap(employee => services.map(service => ({ employee_id: employee.id, service_id: service.id,
      meets_recorded_requirements: !service.required_skills.length || !!employee.skills.length,
      missing_skills: service.required_skills.filter(code => !employee.skills.includes(code)),
    }))),
  };
}

test("matrix validator rejects foreign, incomplete, duplicate and contradictory recorded coverage", () => {
  const original = matrix();
  assert.equal(validSkillMatrix(original, "inst", 0, 0), true);
  assert.equal(validSkillMatrix(matrix("inst", 10, 5), "inst", 10, 5), true);
  assert.equal(validSkillMatrix(matrix("inst", 20, 10), "inst", 20, 10), true);
  const corruptions: ((value: SkillMatrix) => void)[] = [
    value => { value.institute_id = "foreign"; }, value => { value.generated_at = "2026-10-07T22:30:00"; },
    value => { value.employee_page.total = 2; }, value => { value.service_page.limit = 25; },
    value => { value.employees[1].id = value.employees[0].id; }, value => { value.services[1].id = value.services[0].id; },
    value => { value.cells.pop(); }, value => { value.cells[1] = value.cells[0]; },
    value => { value.cells[0].employee_id = "foreign"; }, value => { value.cells[0].meets_recorded_requirements = false; },
    value => { value.cells[5].missing_skills = []; }, value => { value.services[0].requirement_state = "none_recorded"; },
    value => { value.employees[0].skills.push("SPECIAL"); },
    value => { value.employees[0].first_name = " "; },
  ];
  for (const corrupt of corruptions) { const value = structuredClone(original); corrupt(value); assert.equal(validSkillMatrix(value, "inst", 0, 0), false); }
});

test("native matrix is readonly for reception, distinguishes missing and unspecified requirements and hides failed facts", async () => {
  const originalFetch = globalThis.fetch, root = createRoot(document.getElementById("root")!);
  let reads = 0, fail = false;
  globalThis.fetch = async (_url, init) => {
    reads++; assert.equal(init?.method, "GET"); assert.equal(new Headers(init?.headers).get("Authorization"), `Bearer ${token("accueil")}`);
    if (fail) throw new Error("Lecture refusée");
    return response(matrix("inst", 0, 0, 2, 2));
  };
  try {
    setAccessToken(token("collaboratrice"));
    await act(async () => root.render(<SkillMatrixPanel instituteId="inst" />));
    setAccessToken(token("accueil"));
    await act(async () => root.render(<SkillMatrixPanel instituteId="" />));
    assert.equal(reads, 0);
    await act(async () => root.render(<SkillMatrixPanel instituteId="inst" timezone="Europe/Zurich" />));
    assert.match(document.querySelector('td[aria-label="Employee 0 · Service 0"]')!.textContent!, /Exigences couvertes/);
    assert.match(document.querySelector('td[aria-label="Employee 1 · Service 0"]')!.textContent!, /Manque : SPECIAL/);
    assert.match(document.querySelector('td[aria-label="Employee 1 · Service 1"]')!.textContent!, /Aucune exigence enregistrée/);
    assert.match(document.body.textContent!, /ni une certification ni la disponibilité/);
    assert.match(document.body.textContent!, /08\.10\.2026/);
    assert.equal(document.querySelector("input,select,textarea"), null);
    fail = true;
    await act(async () => button("Actualiser les compétences").click());
    assert.equal(document.querySelector("table"), null);
    assert.match(document.querySelector('[role="alert"]')!.textContent!, /refusée/);
    fail = false;
    await act(async () => button("Réessayer").click());
    assert.ok(document.querySelector("table"));
  } finally { await act(async () => root.unmount()); globalThis.fetch = originalFetch; setAccessToken(null); }
});

test("matrix pages employee and service axes independently and rejects a malformed fresh page", async () => {
  const originalFetch = globalThis.fetch, root = createRoot(document.getElementById("root")!);
  const requests: [number, number][] = []; let malformed = false;
  globalThis.fetch = async url => {
    const query = new URL(String(url)).searchParams, employeeOffset = Number(query.get("employee_offset")), serviceOffset = Number(query.get("service_offset"));
    requests.push([employeeOffset, serviceOffset]);
    const value = matrix("inst", employeeOffset, serviceOffset);
    if (malformed) value.cells[0].service_id = "foreign";
    return response(value);
  };
  try {
    setAccessToken(token());
    await act(async () => root.render(<SkillMatrixPanel instituteId="inst" />));
    await act(async () => button("Collaboratrices suivantes").click());
    assert.match(document.body.textContent!, /Collaboratrices : 11–12 \/ 12/);
    assert.equal(button("Collaboratrices suivantes").disabled, true);
    await act(async () => button("Prestations suivantes").click());
    assert.match(document.body.textContent!, /Prestations : 6–7 \/ 7/);
    assert.equal(document.querySelectorAll("tbody tr").length, 2);
    assert.equal(document.querySelectorAll("tbody td").length, 4);
    assert.deepEqual(requests, [[0, 0], [10, 0], [10, 5]]);
    malformed = true;
    await act(async () => button("Prestations précédentes").click());
    assert.equal(document.querySelector("table"), null);
    assert.match(document.querySelector('[role="alert"]')!.textContent!, /incohérente/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = originalFetch; setAccessToken(null); }
});

test("old institute and old access-token reads cannot publish matrix facts", async () => {
  const originalFetch = globalThis.fetch, root = createRoot(document.getElementById("root")!);
  const pending: ((value: Response) => void)[] = [];
  globalThis.fetch = async () => new Promise(resolve => pending.push(resolve));
  try {
    setAccessToken(token());
    await act(async () => root.render(<SkillMatrixPanel instituteId="inst" />));
    await act(async () => root.render(<SkillMatrixPanel instituteId="other" />));
    await act(async () => pending[0](response(matrix("inst"))));
    assert.equal(document.querySelector("table"), null);
    await act(async () => pending[1](response(matrix("other", 0, 0, 1, 1))));
    assert.ok(document.querySelector("table"));
    await act(async () => button("Actualiser les compétences").click());
    setAccessToken(token("responsable_institut", "new-manager"));
    await act(async () => pending[2](response(matrix("other", 0, 0, 1, 1))));
    assert.equal(document.querySelector("table"), null);
    await act(async () => root.render(<SkillMatrixPanel instituteId="other" />));
    await act(async () => root.unmount());
    await act(async () => pending[3](response(matrix("other"))));
    assert.equal(document.querySelector("table"), null);
  } finally { globalThis.fetch = originalFetch; setAccessToken(null); }
});
