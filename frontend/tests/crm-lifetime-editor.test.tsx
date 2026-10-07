import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import React, { act } from "react";
import { CrmLifetimeEditor, lifetimeDuration } from "../src/components/CrmLifetimeEditor";
import { setAccessToken } from "../src/api/session";
import type { LifetimeTerms, LifetimeOriginal } from "../src/crm-lifetime-utils";
const dom=new JSDOM("<!doctype html><div id='root'></div>",{url:"http://localhost:5173"});
Object.assign(globalThis,{window:dom.window,document:dom.window.document,sessionStorage:dom.window.sessionStorage,IS_REACT_ACT_ENVIRONMENT:true});
const { createRoot }=await import("react-dom/client");
const token=(actor="manager")=>`h.${Buffer.from(JSON.stringify({sub:actor,role:"responsable_institut"})).toString("base64url")}.s`;
const storage='flowpilot.crm-lifetime-request:["i","customer_a","manager"]';
const terms: LifetimeTerms={assumptions:{institute_id:"i",customer_id:"customer_a",model:"constant_observed_rate_finite_remaining_lifetime_undiscounted_v1",currency:"CHF",
  expected_active_us:"9007199254740993",activity_fraction:{numerator:"1",denominator:"3"},gross_contribution_margin:{numerator:"2",denominator:"7"},future_relationship_cost_minor:"9007199254740993"},
  previous_id:null,reason:"Declared scenario",idempotency_key:"original"};
const original: LifetimeOriginal={...terms,id:"original",institute_id:"i",customer_id:"customer_a",actor_id:"manager",created_at:"2026-10-07T00:00:00Z"};
const reply=(v: unknown)=>new Response(JSON.stringify(v),{headers:{"Content-Type":"application/json"}});
const click=async(name: string)=>act(async()=>[...document.querySelectorAll<HTMLButtonElement>("button")].find(b=>b.textContent===name)!.click());
test("lost lifetime POST remount recovers original without repeating write and preserves failed current verification",async()=>{
  const fetch=globalThis.fetch; let root=createRoot(document.getElementById("root")!),committed=false,posts=0,failCurrent=false,changed=0;
  sessionStorage.clear();sessionStorage.setItem(storage,JSON.stringify(terms));setAccessToken(token());
  globalThis.fetch=async(url,options)=>{
    if(options?.method==="POST"){posts++;committed=true;throw new Error("Lost reply");}
    if(String(url).endsWith("/current")&&failCurrent)throw new Error("Selected read unavailable");
    return reply(committed?original:null);
  };
  try{
    await act(async()=>root.render(<CrmLifetimeEditor institute="i" customer="customer_a" onChanged={()=>changed++}/>));
    await click("Reprendre la demande CLV conservée");assert.equal(posts,1);assert.ok(sessionStorage.getItem(storage));
    await act(async()=>root.unmount());root=createRoot(document.getElementById("root")!);
    await act(async()=>root.render(<CrmLifetimeEditor institute="i" customer="customer_a" onChanged={()=>changed++}/>));
    failCurrent=true;await click("Reprendre la demande CLV conservée");assert.ok(sessionStorage.getItem(storage));assert.equal(changed,0);
    failCurrent=false;await click("Reprendre la demande CLV conservée");assert.equal(posts,1);assert.equal(sessionStorage.getItem(storage),null);assert.equal(changed,1);
    await click("Préparer une correction CLV");
    const inputs=[...document.querySelectorAll<HTMLInputElement>("input")].map(i=>i.value);
    assert.deepEqual(inputs,["9007199254.740993","1","3","2","7","90071992547409.93",""]);
    assert.equal(lifetimeDuration(inputs[0],"secondes"),terms.assumptions.expected_active_us);
  }finally{await act(async()=>root.unmount());globalThis.fetch=fetch;sessionStorage.clear();}
});
test("lifetime protected intent refuses another actor and corrupt storage; exact duration conversion",async()=>{
  const fetch=globalThis.fetch,root=createRoot(document.getElementById("root")!);let posts=0;
  globalThis.fetch=async(_,options)=>{if(options?.method==="POST")posts++;return reply(original);};
  sessionStorage.clear();sessionStorage.setItem('flowpilot.crm-lifetime-request:["i","customer_a","new"]',JSON.stringify(terms));setAccessToken(token("new"));
  try{
    await act(async()=>root.render(<CrmLifetimeEditor institute="i" customer="customer_a"/>));
    await click("Reprendre la demande CLV conservée");assert.match(document.body.textContent!,/à vérifier/);assert.equal(posts,0);
    sessionStorage.setItem(storage,"{}");setAccessToken(token());await act(async()=>root.render(<CrmLifetimeEditor institute="i" customer="customer_a"/>));
    assert.match(document.body.textContent!,/Demande conservée invalide/);assert.equal(posts,0);
    assert.equal(lifetimeDuration("0.000001","secondes"),"1");assert.equal(lifetimeDuration("1.5","jours"),"129600000000");
    assert.equal(lifetimeDuration("0","jours"),undefined);assert.equal(lifetimeDuration("1e4","jours"),undefined);
  }finally{await act(async()=>root.unmount());globalThis.fetch=fetch;sessionStorage.clear();}
});
