import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import React, { act } from "react";
import { EmployeeOccupationPanel } from "../src/components/EmployeeOccupationPanel";
import { setAccessToken } from "../src/api/session";
import { props, snapshot } from "./occupation-fixture";
const dom = new JSDOM("<!doctype html><div id='root'></div>", { url: "http://localhost:5173" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (role = "responsable_institut", actor = "manager") => `h.${Buffer.from(JSON.stringify({ role, sub: actor })).toString("base64url")}.s`;
const reply = (employee: string) => { const r = snapshot(); r.work_hours.employee_id = employee; r.work_hours.rows[0].interval.employee_id = employee;
  return new Response(JSON.stringify(r), { headers: { "Content-Type": "application/json" } }); };
test("native occupation denies reception reads, isolates late scope/actor replies and hides failed fresh facts", async () => {
  const fetch = globalThis.fetch, root = createRoot(document.getElementById("root")!), pending: ((v: Response) => void)[] = [];
  globalThis.fetch = async () => new Promise(resolve => pending.push(resolve));
  try {
    setAccessToken(token("accueil")); await act(async () => root.render(<EmployeeOccupationPanel {...props} />)); assert.equal(pending.length, 0);
    setAccessToken(token()); await act(async () => root.render(<EmployeeOccupationPanel {...props} />));
    await act(async () => root.render(<EmployeeOccupationPanel {...props} employee="other" />));
    await act(async () => pending[0](reply("emp"))); assert.doesNotMatch(document.body.textContent!, /50,00/);
    setAccessToken(token("responsable_institut", "new")); await act(async () => root.render(<EmployeeOccupationPanel {...props} employee="other" />));
    await act(async () => pending[1](reply("other"))); assert.doesNotMatch(document.body.textContent!, /50,00/);
    await act(async () => pending[2](reply("other"))); assert.match(document.body.textContent!, /50,00 %/); assert.match(document.body.textContent!, /2 h 00 min 00 s/);
    await act(async () => document.querySelector<HTMLButtonElement>("button")!.click()); assert.doesNotMatch(document.body.textContent!, /50,00/);
    await act(async () => pending[3](reply("foreign"))); assert.match(document.body.textContent!, /à vérifier/); assert.equal(document.querySelectorAll("li").length, 0);
  } finally { await act(async () => root.unmount()); globalThis.fetch = fetch; }
});
