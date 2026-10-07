import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import React, { act } from "react";
import { CrmLifetimePanel, lifetimeMoney } from "../src/components/CrmLifetimePanel";
import { setAccessToken } from "../src/api/session";
import { crmLifetime } from "./crm-lifetime-fixture";
const dom=new JSDOM("<!doctype html><div id='root'></div>",{url:"http://localhost:5173"});
Object.assign(globalThis,{window:dom.window,document:dom.window.document,sessionStorage:dom.window.sessionStorage,IS_REACT_ACT_ENVIRONMENT:true});
const { createRoot }=await import("react-dom/client");
const token=(actor="manager")=>`h.${Buffer.from(JSON.stringify({sub:actor,role:"responsable_institut"})).toString("base64url")}.s`;
const props={institute:"i",customer:"customer_a",start:"2026-10-06T00:00:00Z"};
const reply=(v: unknown)=>new Response(JSON.stringify(v),{headers:{"Content-Type":"application/json"}});
test("native scenario disposes old actors, hides fresh forgeries and preserves signed exact negative value",async()=>{
  const fetch=globalThis.fetch,root=createRoot(document.getElementById("root")!),pending: ((v: Response)=>void)[]=[];
  globalThis.fetch=async url=>String(url).includes("/lifetime-assumptions/")?reply(null):new Promise(resolve=>pending.push(resolve));
  try{
    setAccessToken(token());await act(async()=>root.render(<CrmLifetimePanel {...props}/>));
    setAccessToken(token("new"));await act(async()=>root.render(<CrmLifetimePanel {...props}/>));
    await act(async()=>pending[0](reply(crmLifetime())));assert.doesNotMatch(document.body.textContent!,/CLV restante conditionnelle/);
    await act(async()=>pending[1](reply(crmLifetime())));assert.match(document.body.textContent!,/CLV restante conditionnelle : −0,66 CHF/);
    assert.match(document.body.textContent!,/Valeur exacte en centimes : -199 \/ 3/);
    await act(async()=>[...document.querySelectorAll<HTMLButtonElement>("button")].find(b=>b.textContent==="Actualiser le scénario CLV")!.click());
    assert.doesNotMatch(document.body.textContent!,/CLV restante conditionnelle/);
    const forged=crmLifetime();forged.scenario!.remaining_clv_minor!.numerator="199";
    await act(async()=>pending[2](reply(forged)));assert.match(document.body.textContent!,/Scénario CLV à vérifier/);
    await act(async()=>root.render(<CrmLifetimePanel {...props} customer="other"/>));
    await act(async()=>pending[3](reply(crmLifetime())));assert.match(document.body.textContent!,/Scénario CLV à vérifier/);
    assert.equal(lifetimeMoney({numerator:"-1",denominator:"2"},"CHF"),"−0,01 CHF");
    assert.equal(lifetimeMoney({numerator:"9007199254740993",denominator:"1"},"EUR"),"90071992547409,93 EUR");
  }finally{await act(async()=>root.unmount());globalThis.fetch=fetch;sessionStorage.clear();}
});
test("no verified observation period means no scenario request and no invented value",async()=>{
  const fetch=globalThis.fetch,root=createRoot(document.getElementById("root")!);const urls: string[]=[];
  globalThis.fetch=async url=>{urls.push(String(url));return reply(null);};
  try{setAccessToken(token());await act(async()=>root.render(<CrmLifetimePanel institute="i" customer="customer_a"/>));
    assert.equal(urls.some(u=>u.includes("lifetime-scenario")),false);assert.match(document.body.textContent!,/configurez une période CRM vérifiable/);
  }finally{await act(async()=>root.unmount());globalThis.fetch=fetch;}
});
