import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import React, { act } from "react";
import { RebookingChoices, type RebookingSelection } from "../src/components/RebookingChoices";
import { setAccessToken } from "../src/api/session";
import { props } from "./rebooking-fixture";
import { sources, targets } from "./rebooking-options-fixture";
const dom = new JSDOM("<!doctype html><div id='root'></div>", { url: "http://localhost:5173" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (role = "responsable_institut", actor = "manager") => `h.${Buffer.from(JSON.stringify({ role, sub: actor })).toString("base64url")}.s`;
const response = (v: unknown) => new Response(JSON.stringify(v), { headers: { "Content-Type": "application/json" } });
const sourceReply = (employee: string) => { const r = sources(); r.employee_id = employee; r.rows[0].capture!.employee_id = employee; return response(r); };
const targetReply = (employee: string) => { const r = targets(); r.source.employee_id = employee; return response(r); };
test("native choices isolate actor/employee/refresh responses and withdraw selections on failed fresh source reads", async () => {
  const fetch = globalThis.fetch, root = createRoot(document.getElementById("root")!), pending: ((v: Response) => void)[] = [];
  const selected: (RebookingSelection | undefined)[] = [];
  globalThis.fetch = async () => new Promise(resolve => pending.push(resolve));
  const render = (employee = "emp", disabled = false) => <RebookingChoices {...props} employee={employee} disabled={disabled} onSelection={v => selected.push(v)} />;
  const choose = async (value: string, index = 0) => act(async () => { const select = document.querySelectorAll("select")[index]; select.value = value; select.dispatchEvent(new dom.window.Event("change", { bubbles: true })); });
  try {
    setAccessToken(token("accueil")); await act(async () => root.render(render())); assert.equal(pending.length, 0);
    setAccessToken(token()); await act(async () => root.render(render()));
    await act(async () => root.render(render("other"))); await act(async () => pending[0](sourceReply("emp"))); assert.equal(document.querySelector("select"), null);
    setAccessToken(token("responsable_institut", "new")); await act(async () => root.render(render("other")));
    await act(async () => pending[1](sourceReply("other"))); assert.equal(document.querySelector("select"), null);
    await act(async () => pending[2](sourceReply("other"))); await choose("session:session");
    await act(async () => document.querySelector<HTMLButtonElement>("button")!.click());
    await act(async () => pending[3](targetReply("other"))); assert.equal(document.querySelectorAll("select").length, 0); assert.equal(selected.some(Boolean), false);
    await act(async () => pending[4](sourceReply("other"))); await choose("session:session");
    await act(async () => pending[5](targetReply("other"))); await choose("target", 1);
    assert.equal(selected[selected.length-1]!.source.employee_id, "other"); assert.equal(selected[selected.length-1]!.target.appointment_id, "target");
    await act(async () => document.querySelector<HTMLButtonElement>("button")!.click()); assert.equal(selected[selected.length-1], undefined);
    const bad = sources(); bad.employee_id = "other"; bad.rows[0].capture!.employee_id = "other"; bad.rows[0].customer_known = false;
    await act(async () => pending[6](response(bad))); assert.match(document.body.textContent!, /à vérifier/); assert.equal(document.querySelector("select"), null);
    await act(async () => root.render(render("other", true))); assert.equal(pending.length, 7);
  } finally { await act(async () => root.unmount()); globalThis.fetch = fetch; }
});
