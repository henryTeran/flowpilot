import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import React, { act } from "react";
import { CrmReturnPanel, returnDays } from "../src/components/CrmReturnPanel";
import { setAccessToken } from "../src/api/session";
import { crmEmptyReturn } from "./crm-fixture";
const dom = new JSDOM("<!doctype html><div id='root'></div>", { url: "http://localhost:5173" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (actor="manager", role="responsable_institut") => `h.${Buffer.from(JSON.stringify({ sub: actor, role })).toString("base64url")}.s`;
const props = { institute: "i", customer: "customer_a", start: "2026-10-06T00:00:00Z", end: "2026-10-07T00:00:00Z" };
const reply = (v: unknown) => new Response(JSON.stringify(v), { headers: { "Content-Type": "application/json" } });
test("native return read refuses old actor/customer, forged mean and preserves explicit uncertainty", async () => {
  const original = globalThis.fetch, root = createRoot(document.getElementById("root")!);
  const pending: ((v: Response) => void)[] = [], urls: string[] = [];
  globalThis.fetch = async url => { urls.push(String(url)); return new Promise(resolve => pending.push(resolve)); };
  try {
    setAccessToken(token("m","accueil")); await act(async () => root.render(<CrmReturnPanel {...props} />)); assert.equal(pending.length,0);
    setAccessToken(token()); await act(async () => root.render(<CrmReturnPanel {...props} />));
    setAccessToken(token("new")); await act(async () => root.render(<CrmReturnPanel {...props} />));
    await act(async () => pending[0](reply(crmEmptyReturn()))); assert.doesNotMatch(document.body.textContent!,/Épisodes de soins enregistrés/);
    await act(async () => pending[1](reply(crmEmptyReturn()))); assert.match(document.body.textContent!,/Non déterminé/);
    assert.match(document.body.textContent!,/couverture des soins et l’historique sont incomplets/);
    await act(async () => document.querySelector<HTMLButtonElement>("button")!.click()); assert.doesNotMatch(document.body.textContent!,/Épisodes de soins enregistrés/);
    const forged = crmEmptyReturn(); forged.summary.average_return_gap_us = { numerator: "0", denominator: "1" };
    await act(async () => pending[2](reply(forged))); assert.match(document.body.textContent!,/à vérifier/);
    await act(async () => root.render(<CrmReturnPanel {...props} customer="customer_b" />));
    await act(async () => pending[3](reply(crmEmptyReturn()))); assert.match(document.body.textContent!,/à vérifier/);
    assert.match(urls[0],/offset=0&limit=20/); assert.match(urls[3],/customers\/customer_b\/return-cycle/);
    assert.equal(returnDays("86400000000","1"),"1,00"); assert.equal(returnDays("432000000","1"),"0,01");
  } finally { await act(async () => root.unmount()); globalThis.fetch = original; }
});
test("native return pages hide preceding rows and retain full-cohort totals", async () => {
  const original = globalThis.fetch, root = createRoot(document.getElementById("root")!);
  const pending: ((v: Response) => void)[] = [], urls: string[] = [];
  globalThis.fetch = async url => { urls.push(String(url)); return new Promise(resolve => pending.push(resolve)); };
  const page = (offset: number) => {
    const r = crmEmptyReturn(); r.summary.execution_count = r.summary.episode_count = r.page.total = 21;
    r.summary.known_gap_count = 20; r.summary.known_gap_total_us = "20000000"; r.summary.average_return_gap_us = { numerator: "20000000", denominator: "20" };
    r.page.offset = offset;
    r.episodes = Array.from({ length: offset ? 1 : 20 }, (_, j) => { const i = offset+j;
      return { ticket_id: `ticket_${i}`, started_at: `2026-10-06T00:00:${String(i*2).padStart(2,"0")}Z`, completed_at: `2026-10-06T00:00:${String(i*2+1).padStart(2,"0")}Z`, execution_count: 1, service_ids: ["care"] }; });
    r.gaps = r.episodes.filter(e => e.ticket_id !== "ticket_0").map(e => { const i=Number(e.ticket_id.split("_")[1]); return { previous_ticket_id: `ticket_${i-1}`, next_ticket_id: e.ticket_id, gap_us: "1000000", quality: "known" as const }; }); return r;
  };
  try {
    setAccessToken(token()); await act(async () => root.render(<CrmReturnPanel {...props} />));
    await act(async () => pending[0](reply(page(0)))); assert.equal(document.querySelectorAll("li").length,20);
    await act(async () => [...document.querySelectorAll<HTMLButtonElement>("button")].find(b => b.textContent === "Épisodes suivants")!.click());
    assert.equal(document.querySelectorAll("li").length,0); assert.match(urls[1],/offset=20/);
    await act(async () => pending[1](reply(page(20)))); assert.equal(document.querySelectorAll("li").length,1);
    assert.match(document.body.textContent!,/21–21 sur 21/); assert.match(document.body.textContent!,/Depuis le ticket ticket_19/);
    assert.match(document.body.textContent!,/Épisodes de soins enregistrés : 21/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = original; }
});
