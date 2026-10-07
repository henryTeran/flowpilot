import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import React,{ act } from "react";
import { CrmLifecyclePanel } from "../src/components/CrmLifecyclePanel";
import { setAccessToken } from "../src/api/session";
import { crmLifecycle } from "./crm-lifecycle-fixture";
const dom = new JSDOM("<!doctype html><div id='root'></div>",{url:"http://localhost:5173"});
Object.assign(globalThis,{window:dom.window,document:dom.window.document,sessionStorage:dom.window.sessionStorage,IS_REACT_ACT_ENVIRONMENT:true});
const {createRoot}=await import("react-dom/client");
const token=(actor="manager")=>`h.${Buffer.from(JSON.stringify({sub:actor,role:"responsable_institut"})).toString("base64url")}.s`;
const reply=(v: unknown)=>new Response(JSON.stringify(v),{headers:{"Content-Type":"application/json"}});
test("native birthday hides forged fresh observation, recovers and disposes old actor/customer responses",async()=>{
  const fetch=globalThis.fetch,root=createRoot(document.getElementById("root")!);let forged=false;
  const pending: ((v: Response)=>void)[]=[];let defer=false;
  globalThis.fetch=async url=>{if(String(url).includes("/lifecycle-declarations/"))return reply(null);
    if(defer)return new Promise(resolve=>pending.push(resolve));const r=crmLifecycle();if(forged)r.birthday!.due=false;return reply(r);};
  const refresh=()=>act(async()=>[...document.querySelectorAll<HTMLButtonElement>("button")].find(b=>b.textContent==="Actualiser l’observation anniversaire")!.click());
  try{
    setAccessToken(token());await act(async()=>root.render(<CrmLifecyclePanel institute="i" customer="customer_a"/>));
    assert.match(document.body.textContent!,/Anniversaire dans la journée locale/);assert.match(document.body.textContent!,/Europe\/Zurich/);
    forged=true;await refresh();assert.doesNotMatch(document.body.textContent!,/Journée locale/);assert.match(document.body.textContent!,/à vérifier/);
    forged=false;await refresh();assert.match(document.body.textContent!,/Journée locale/);
    defer=true;await refresh();setAccessToken(token("other"));await act(async()=>root.render(<CrmLifecyclePanel institute="i" customer="customer_a"/>));
    await act(async()=>pending[0](reply(crmLifecycle())));assert.doesNotMatch(document.body.textContent!,/Journée locale/);
    await act(async()=>pending[1](reply(crmLifecycle())));assert.match(document.body.textContent!,/Journée locale/);
    await act(async()=>root.render(<CrmLifecyclePanel institute="i" customer="customer_b"/>));
    await act(async()=>pending[2](reply(crmLifecycle())));assert.doesNotMatch(document.body.textContent!,/Journée locale/);assert.match(document.body.textContent!,/à vérifier/);
  }finally{await act(async()=>root.unmount());globalThis.fetch=fetch;}
});
