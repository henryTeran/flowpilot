import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import React,{ act } from "react";
import { CrmEventPanel } from "../src/components/CrmEventPanel";
import { setAccessToken } from "../src/api/session";

const dom=new JSDOM("<!doctype html><div id='root'></div>",{url:"http://localhost:5173"});
Object.assign(globalThis,{window:dom.window,document:dom.window.document,sessionStorage:dom.window.sessionStorage,IS_REACT_ACT_ENVIRONMENT:true});
const {createRoot}=await import("react-dom/client");
const token=(actor="manager")=>`h.${Buffer.from(JSON.stringify({sub:actor,role:"responsable_institut"})).toString("base64url")}.s`;
const storage='flowpilot.crm-event-request:["i","c","manager"]';
const terms={action:"reconcile",event_key:null,expected_revision_id:null,reason:"Explicit reconciliation",idempotency_key:"original"};
const customer={institute_id:"i",customer_id:"c",created_at:"2020-01-01T00:00:00Z"},clock="2026-10-07T00:00:00Z";
const source={institute_id:"i",customer_id:"c",captured_at:clock,customer,policy_original:null,lifecycle:{institute_id:"i",customer_id:"c",captured_at:clock,customer,original:null,calendar_original:null,birthday:null,unavailable_reason:"declaration_absent",delivery_authorized:false,external_message_sent:false},anchors:[],candidates:[],diagnostics:{policy_absent:1,future_policy:0,future_registration:0,birthday_unavailable:1,care_unavailable:1,care_unlinked_ticket:0,care_invalid_owner_or_service:0,care_invalid_actual_times:0,invalid_event_timing:0,package_absent:1,membership_absent:1,invalid_package:0,invalid_membership:0},complete_customer_history:false,delivery_authorized:false,external_message_sent:false};
const original={id:"original",institute_id:"i",customer_id:"c",actor_id:"manager",request:terms,captured_at:clock,source,revisions:[]};
const page={institute_id:"i",customer_id:"c",total:0,offset:0,limit:20,revisions:[]};
const reply=(v: unknown)=>new Response(JSON.stringify(v),{headers:{"Content-Type":"application/json"}});
const click=async(name: string)=>act(async()=>[...document.querySelectorAll<HTMLButtonElement>("button")].find(b=>b.textContent===name)!.click());
test("event lost POST remount recovers once; failed current read retains intent until verified reread",async()=>{
  const fetch=globalThis.fetch;let root=createRoot(document.getElementById("root")!),committed=false,posts=0,failCurrent=false;
  sessionStorage.clear();sessionStorage.setItem(storage,JSON.stringify(terms));setAccessToken(token());
  globalThis.fetch=async(url,options)=>{if(options?.method==="POST"){posts++;committed=true;throw new Error("Lost reply");}
    if(String(url).includes("/events?")&&failCurrent)throw new Error("Selected event unavailable");return reply(String(url).includes("/events?") ? page : committed?original:null);};
  try{
    await act(async()=>root.render(<CrmEventPanel institute="i" customer="c"/>));
    await click("Reprendre l'action conservée");assert.equal(posts,1);assert.ok(sessionStorage.getItem(storage));
    await act(async()=>root.unmount());root=createRoot(document.getElementById("root")!);
    await act(async()=>root.render(<CrmEventPanel institute="i" customer="c"/>));
    failCurrent=true;await click("Reprendre l'action conservée");assert.ok(sessionStorage.getItem(storage));
    failCurrent=false;await click("Reprendre l'action conservée");assert.equal(posts,1);assert.equal(sessionStorage.getItem(storage),null);assert.match(document.body.textContent!,/Capture originale vérifiée/);
  }finally{await act(async()=>root.unmount());globalThis.fetch=fetch;sessionStorage.clear();}
});
test("event rejects inconsistent microsecond original and keeps protected intent",async()=>{
  const fetch=globalThis.fetch,root=createRoot(document.getElementById("root")!);let reads=0,posts=0;
  sessionStorage.clear();sessionStorage.setItem(storage,JSON.stringify(terms));setAccessToken(token());
  globalThis.fetch=async(url,options)=>{if(options?.method==="POST")posts++;
    if(String(url).includes("/original/")){reads++;return reply(reads===1?original:{...original,captured_at:"2026-10-07T00:00:00.000001Z"});}return reply(String(url).includes("/events?") ? page : original);};
  try{await act(async()=>root.render(<CrmEventPanel institute="i" customer="c"/>));await click("Reprendre l'action conservée");
    assert.match(document.body.textContent!,/Original relu à vérifier/);assert.ok(sessionStorage.getItem(storage));assert.equal(posts,0);
  }finally{await act(async()=>root.unmount());globalThis.fetch=fetch;sessionStorage.clear();}
});

test("event recovery rejects actor and independent ID disagreement without a new write",async()=>{
 const fetch=globalThis.fetch;let root=createRoot(document.getElementById("root")!),posts=0;
 setAccessToken(token());
 try{for(const forged of [{...original,actor_id:"foreign"},{...original,id:"different"}]){
  sessionStorage.clear();sessionStorage.setItem(storage,JSON.stringify(terms));setAccessToken(token());
  globalThis.fetch=async(url,options)=>{if(options?.method==="POST")posts++;const path=String(url);return reply(path.includes("/events?")?page:path.endsWith("/event-captures/original")?forged:original);};
  await act(async()=>root.render(<CrmEventPanel institute="i" customer="c"/>));await click("Reprendre l'action conserv\u00e9e");
  assert.ok(sessionStorage.getItem(storage));assert.equal(posts,0);
  await act(async()=>root.unmount());root=createRoot(document.getElementById("root")!);
 }}finally{await act(async()=>root.unmount());globalThis.fetch=fetch;sessionStorage.clear();}
});
