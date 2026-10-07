import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import React, { act } from "react";
import { SkillEditorPanel, validSkillTerms, validSkillCodes } from "../src/components/SkillEditorPanel";
import { setAccessToken } from "../src/api/session";
const dom = new JSDOM("<!doctype html><div id='root'></div>", { url: "http://localhost:5173" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (sub = "manager") => `h.${Buffer.from(JSON.stringify({ role: "responsable_institut", sub })).toString("base64url")}.s`;
const response = (value: unknown) => new Response(JSON.stringify(value), { headers: { "Content-Type": "application/json" } });
const storage = 'flowpilot.skill-change:["inst","manager"]';
const staff = [{ id: "emp", institute_id: "inst", first_name: "Angela", skills: [], status: "available" }];
const terms = { employee_id: "emp", expected_skills: ["OLD"], skills: ["NEW"], reason: "Declared", idempotency_key: "original" };
const original = { ...terms, id: "change", institute_id: "inst", actor_id: "manager", created_at: "2026-10-07T12:00:00Z" };
const button = (label: string) => [...document.querySelectorAll<HTMLButtonElement>("button")].find(row => row.textContent === label)!;

test("skill editor validates exact declared sets and rejects missing comparison conditions", () => {
  assert.equal(validSkillTerms(terms), true);
  assert.equal(validSkillTerms({ ...terms, expected_skills: undefined }), false);
  for (const value of [["DUP", "DUP"], [" "], ["x".repeat(65)], Array.from({ length: 101 }, (_, index) => String(index))]) assert.equal(validSkillCodes(value), false);
  assert.equal(validSkillCodes([]), true);
});

test("skill editor preserves contradictory original and requires fresh current read before clearing", async () => {
  const fetch = globalThis.fetch, root = createRoot(document.getElementById("root")!); let changed = true, corrupt = false, posts = 0;
  globalThis.fetch = async (url, init) => { if (init?.method === "POST") posts++;
    return response(String(url).includes("/original/") ? { ...original, reason: changed ? "Wrong reason" : original.reason }
      : { skills: corrupt ? ["DUP", "DUP"] : ["LATER"] }); };
  try {
    sessionStorage.clear(); setAccessToken(token()); sessionStorage.setItem(storage, JSON.stringify(terms));
    await act(async () => root.render(<SkillEditorPanel institute="inst" employees={staff} onChanged={async () => true} />));
    await act(async () => button("Reprendre la modification conservée").click());
    assert.ok(sessionStorage.getItem(storage)); assert.equal(posts, 0); assert.match(document.body.textContent!, /originale.*vérifier/);
    changed = false; corrupt = true; await act(async () => button("Reprendre la modification conservée").click());
    assert.ok(sessionStorage.getItem(storage)); assert.equal(document.querySelector("form"), null);
    corrupt = false; await act(async () => button("Relire les compétences").click());
    await act(async () => button("Reprendre la modification conservée").click());
    assert.equal(posts, 0); assert.equal(sessionStorage.getItem(storage), null);
    assert.match(document.body.textContent!, /Compétences actuelles : LATER/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = fetch; }
});

test("late previous actor read cannot post or clear a saved skill change", async () => {
  const fetch = globalThis.fetch, root = createRoot(document.getElementById("root")!); let posts = 0, release!: (value: Response) => void;
  globalThis.fetch = async (url, init) => { if (init?.method === "POST") posts++;
    return String(url).includes("/original/") ? new Promise(resolve => { release = resolve; }) : response({ skills: ["OLD"] }); };
  try {
    sessionStorage.clear(); setAccessToken(token()); sessionStorage.setItem(storage, JSON.stringify(terms));
    await act(async () => root.render(<SkillEditorPanel institute="inst" employees={staff} onChanged={async () => true} />));
    await act(async () => { button("Reprendre la modification conservée").click(); await Promise.resolve(); });
    setAccessToken(token("new-manager")); await act(async () => root.render(<SkillEditorPanel institute="inst" employees={staff} onChanged={async () => true} />));
    await act(async () => release(response(null))); assert.equal(posts, 0); assert.ok(sessionStorage.getItem(storage));
    assert.equal(button("Reprendre la modification conservée"), undefined);
  } finally { await act(async () => root.unmount()); globalThis.fetch = fetch; }
});
