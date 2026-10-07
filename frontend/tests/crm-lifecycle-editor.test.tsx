import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import React,{ act } from "react";
import { CrmLifecycleEditor } from "../src/components/CrmLifecycleEditor";
import { setAccessToken } from "../src/api/session";
import type { LifecycleTerms,LifecycleOriginal } from "../src/crm-lifecycle-utils";
const dom=new JSDOM("<!doctype html><div id='root'></div>",{url:"http://localhost:5173"});
Object.assign(globalThis,{window:dom.window,document:dom.window.document,sessionStorage:dom.window.sessionStorage,IS_REACT_ACT_ENVIRONMENT:true});
const {createRoot}=await import("react-dom/client");
const token=(actor="manager")=>`h.${Buffer.from(JSON.stringify({sub:actor,role:"responsable_institut"})).toString("base64url")}.s`;
const storage='flowpilot.crm-lifecycle-request:["i","c","manager"]';
const terms: LifecycleTerms={declaration:{institute_id:"i",customer_id:"c",birthday:{month:2,day:29},birthday_evidence:"Customer form",communications:(["email","sms"] as const).flatMap(channel => (["service_follow_up","marketing"] as const).map(purpose => ({channel,purpose,permission:"refused" as const,evidence:"Recorded refusal"})))},previous_id:null,reason:"Explicit declaration",idempotency_key:"original"};
const original: LifecycleOriginal={...terms,id:"original",institute_id:"i",customer_id:"c",actor_id:"manager",created_at:"2026-10-07T00:00:00Z"};
const reply=(v: unknown)=>new Response(JSON.stringify(v),{headers:{"Content-Type":"application/json"}});
const click=async(name: string)=>act(async()=>[...document.querySelectorAll<HTMLButtonElement>("button")].find(b=>b.textContent===name)!.click());
test("lifecycle lost POST remount recovers once; failed current read retains intent until verified callback",async()=>{
  const fetch=globalThis.fetch;let root=createRoot(document.getElementById("root")!),committed=false,posts=0,failCurrent=false,changed=0;
  sessionStorage.clear();sessionStorage.setItem(storage,JSON.stringify(terms));setAccessToken(token());
  globalThis.fetch=async(url,options)=>{if(options?.method==="POST"){posts++;committed=true;throw new Error("Lost reply");}
    if(String(url).endsWith("/current")&&failCurrent)throw new Error("Selected calendar unavailable");return reply(committed?original:null);};
  try{
    await act(async()=>root.render(<CrmLifecycleEditor institute="i" customer="c" onChanged={()=>changed++}/>));
    await click("Reprendre la declaration conservee");assert.equal(posts,1);assert.ok(sessionStorage.getItem(storage));
    await act(async()=>root.unmount());root=createRoot(document.getElementById("root")!);
    await act(async()=>root.render(<CrmLifecycleEditor institute="i" customer="c" onChanged={()=>changed++}/>));
    failCurrent=true;await click("Reprendre la declaration conservee");assert.ok(sessionStorage.getItem(storage));assert.equal(changed,0);
    failCurrent=false;await click("Reprendre la declaration conservee");assert.equal(posts,1);assert.equal(sessionStorage.getItem(storage),null);assert.equal(changed,1);
    await click("Preparer une correction cliente");assert.equal(document.querySelector<HTMLInputElement>("input")!.value,"2");
    assert.equal(document.querySelector<HTMLSelectElement>("select")!.value,"known");
  }finally{await act(async()=>root.unmount());globalThis.fetch=fetch;sessionStorage.clear();}
});
test("lifecycle rejects inconsistent microsecond original and keeps protected intent",async()=>{
  const fetch=globalThis.fetch,root=createRoot(document.getElementById("root")!);let reads=0,posts=0;
  sessionStorage.clear();sessionStorage.setItem(storage,JSON.stringify(terms));setAccessToken(token());
  globalThis.fetch=async(url,options)=>{if(options?.method==="POST")posts++;
    if(String(url).includes("/original/")){reads++;return reply(reads===1?original:{...original,created_at:"2026-10-07T00:00:00.000001Z"});}return reply(original);};
  try{await act(async()=>root.render(<CrmLifecycleEditor institute="i" customer="c"/>));await click("Reprendre la declaration conservee");
    assert.match(document.body.textContent!,/Original relu à vérifier/);assert.ok(sessionStorage.getItem(storage));assert.equal(posts,0);
  }finally{await act(async()=>root.unmount());globalThis.fetch=fetch;sessionStorage.clear();}
});
