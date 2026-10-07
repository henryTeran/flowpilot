import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import React, { act } from "react";
import { EmployeeObjectivesPanel } from "../src/components/EmployeeObjectivesPanel";
import { setAccessToken } from "../src/api/session";
const dom = new JSDOM("<!doctype html><div id='root'></div>", { url: "http://localhost:5173" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (role = "responsable_institut", sub = "manager") => `h.${Buffer.from(JSON.stringify({ role, sub })).toString("base64url")}.s`;
const response = (employee: string) => new Response(JSON.stringify({ institute_id: "inst", employee_id: employee,
  generated_at: "2026-10-07T12:00:00Z", page: { offset: 0, limit: 20, total: 0 }, rows: [] }), { headers: { "Content-Type": "application/json" } });
test("objective profile denies reception reads and isolates old employee/actor replies", async () => {
  const fetch = globalThis.fetch, root = createRoot(document.getElementById("root")!), pending: ((v: Response) => void)[] = [];
  globalThis.fetch = async () => new Promise(resolve => pending.push(resolve));
  try {
    setAccessToken(token("accueil")); await act(async () => root.render(<EmployeeObjectivesPanel institute="inst" employee="emp" />)); assert.equal(pending.length, 0);
    setAccessToken(token()); await act(async () => root.render(<EmployeeObjectivesPanel institute="inst" employee="emp" />));
    await act(async () => root.render(<EmployeeObjectivesPanel institute="inst" employee="other" />));
    await act(async () => pending[0](response("emp"))); assert.doesNotMatch(document.body.textContent!, /Aucun objectif/);
    setAccessToken(token("responsable_institut", "new")); await act(async () => root.render(<EmployeeObjectivesPanel institute="inst" employee="other" />));
    await act(async () => pending[1](response("other"))); assert.doesNotMatch(document.body.textContent!, /Aucun objectif/);
    await act(async () => pending[2](response("other"))); assert.match(document.body.textContent!, /Aucun objectif/);
    await act(async () => document.querySelector<HTMLButtonElement>("button")!.click()); assert.doesNotMatch(document.body.textContent!, /Aucun objectif/);
    await act(async () => pending[3](response("foreign"))); assert.match(document.body.textContent!, /à vérifier/); assert.doesNotMatch(document.body.textContent!, /Aucun objectif/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = fetch; }
});
