import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import React,{ act } from "react";
import { CrmBirthdayPolicyPanel } from "../src/components/CrmBirthdayPolicyPanel";
import { setAccessToken } from "../src/api/session";
import type { BirthdayPolicyTerms,BirthdayPolicyOriginal } from "../src/crm-lifecycle-utils";
const dom=new JSDOM("<!doctype html><div id='root'></div>",{url:"http://localhost:5173"});
Object.assign(globalThis,{window:dom.window,document:dom.window.document,sessionStorage:dom.window.sessionStorage,IS_REACT_ACT_ENVIRONMENT:true});
const {createRoot}=await import("react-dom/client");
const token=(actor="manager")=>`h.${Buffer.from(JSON.stringify({sub:actor,role:"responsable_institut"})).toString("base64url")}.s`;
const storage='flowpilot.crm-birthday-policy-request:["i","manager"]';
const terms: BirthdayPolicyTerms={policy:{institute_id:"i",timezone:"Europe/Zurich",leap_day:"march_1"},previous_policy_id:null,reason:"Explicit calendar",idempotency_key:"original"};
const original: BirthdayPolicyOriginal={...terms,id:"original",institute_id:"i",actor_id:"manager",created_at:"2026-10-07T00:00:00Z"};
const reply=(v: unknown)=>new Response(JSON.stringify(v),{headers:{"Content-Type":"application/json"}});
const click=async(name: string)=>act(async()=>[...document.querySelectorAll<HTMLButtonElement>("button")].find(b=>b.textContent===name)!.click());
test("calendar lost POST remount recovers once; failed current read retains intent until verified callback",async()=>{
  const fetch=globalThis.fetch;let root=createRoot(document.getElementById("root")!),committed=false,posts=0,failCurrent=false,changed=0;
  sessionStorage.clear();sessionStorage.setItem(storage,JSON.stringify(terms));setAccessToken(token());
  globalThis.fetch=async(url,options)=>{if(options?.method==="POST"){posts++;committed=true;throw new Error("Lost reply");}
    if(String(url).endsWith("/current")&&failCurrent)throw new Error("Selected calendar unavailable");return reply(committed?original:null);};
  try{
    await act(async()=>root.render(<CrmBirthdayPolicyPanel institute="i" onChanged={()=>changed++}/>));
    await click("Reprendre le calendrier conservé");assert.equal(posts,1);assert.ok(sessionStorage.getItem(storage));
    await act(async()=>root.unmount());root=createRoot(document.getElementById("root")!);
    await act(async()=>root.render(<CrmBirthdayPolicyPanel institute="i" onChanged={()=>changed++}/>));
    failCurrent=true;await click("Reprendre le calendrier conservé");assert.ok(sessionStorage.getItem(storage));assert.equal(changed,0);
    failCurrent=false;await click("Reprendre le calendrier conservé");assert.equal(posts,1);assert.equal(sessionStorage.getItem(storage),null);assert.equal(changed,1);
    await click("Préparer une correction anniversaire");assert.equal(document.querySelector<HTMLInputElement>("input")!.value,"Europe/Zurich");
    assert.equal(document.querySelector<HTMLSelectElement>("select")!.value,"march_1");
  }finally{await act(async()=>root.unmount());globalThis.fetch=fetch;sessionStorage.clear();}
});
test("calendar rejects inconsistent microsecond original and keeps protected intent",async()=>{
  const fetch=globalThis.fetch,root=createRoot(document.getElementById("root")!);let reads=0,posts=0;
  sessionStorage.clear();sessionStorage.setItem(storage,JSON.stringify(terms));setAccessToken(token());
  globalThis.fetch=async(url,options)=>{if(options?.method==="POST")posts++;
    if(String(url).includes("/original/")){reads++;return reply(reads===1?original:{...original,created_at:"2026-10-07T00:00:00.000001Z"});}return reply(original);};
  try{await act(async()=>root.render(<CrmBirthdayPolicyPanel institute="i"/>));await click("Reprendre le calendrier conservé");
    assert.match(document.body.textContent!,/Original relu à vérifier/);assert.ok(sessionStorage.getItem(storage));assert.equal(posts,0);
  }finally{await act(async()=>root.unmount());globalThis.fetch=fetch;sessionStorage.clear();}
});
