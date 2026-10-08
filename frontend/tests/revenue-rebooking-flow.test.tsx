import test from "node:test";
import assert from "node:assert/strict";
import React,{act} from "react";
import {JSDOM} from "jsdom";
import {readFileSync} from "node:fs";
import {RevenueRebookingReview} from "../src/components/RevenueRebookingReview";
import {setAccessToken} from "../src/api/session";
const vector=JSON.parse(readFileSync(new URL("./fixtures/revenue-rebooking-14v.json",import.meta.url),"utf8"));
const dom=new JSDOM("<div id='root'></div>",{url:"http://localhost"});Object.assign(globalThis,{window:dom.window,document:dom.window.document,sessionStorage:dom.window.sessionStorage,IS_REACT_ACT_ENVIRONMENT:true});
const {createRoot}=await import("react-dom/client");
const token=(role="responsable_institut")=>`h.${Buffer.from(JSON.stringify({sub:"manager",role})).toString("base64url")}.s`;
const reply=(v:unknown)=>new Response(JSON.stringify(v),{headers:{"Content-Type":"application/json"}});
async function click(){await act(async()=>document.querySelector("button")!.click());}
test("manager explicitly reads candidates and separates missing/declared/future permissions from delivery authority",async()=>{
  setAccessToken(token());const root=createRoot(document.getElementById("root")!);let reads=0,value:unknown=vector;
  globalThis.fetch=async(url,init)=>{reads++;assert.equal(init?.method,"GET");assert.match(String(url),/rebooking\?offset=0&limit=20/);return reply(value);};
  try{await act(async()=>root.render(<RevenueRebookingReview institute="own" timezone="UTC"/>));assert.equal(reads,0);await click();assert.match(document.body.textContent!,/7 clientes enregistrées/);
    assert.match(document.body.textContent!,/1 avec retour actif/);assert.match(document.body.textContent!,/02\.01\.2026/);assert.match(document.body.textContent!,/03\.01\.2026/);
    assert.match(document.body.textContent!,/Permission inconnue/);assert.match(document.body.textContent!,/permission déclarée accordée/);assert.match(document.body.textContent!,/permission déclarée refusée/);
    assert.match(document.body.textContent!,/ne constituent pas une autorisation d’envoi/);assert.match(document.body.textContent!,/rule-manager/);assert.match(document.body.textContent!,/care|Soin observé/);
    const future=structuredClone(vector);future.opportunities[1].evidence.lifecycle_original.created_at="2026-01-06T00:00:00Z";value=future;await click();assert.match(document.body.textContent!,/postérieure à la capture/);
    value={...vector,external_message_sent:true};await click();assert.ok(document.querySelector('[role="alert"]'));assert.equal(document.querySelector("article"),null);
    value=vector;await click();assert.ok(document.querySelector("article"));assert.equal(reads,4);
  }finally{await act(async()=>root.unmount());}
});
test("pending rebooking read cannot revive a replaced institute or initiate another read after authority removal",async()=>{
  setAccessToken(token());const root=createRoot(document.getElementById("root")!);let resolve!:(v:Response)=>void,reads=0;
  globalThis.fetch=async()=>{reads++;return new Promise<Response>(r=>{resolve=r;});};
  try{await act(async()=>root.render(<RevenueRebookingReview institute="own" timezone="UTC"/>));await click();assert.ok(document.querySelector('[role="status"]'));
    await act(async()=>root.render(<RevenueRebookingReview institute="new" timezone="UTC"/>));await act(async()=>resolve(reply(vector)));assert.equal(document.querySelector("article"),null);
    setAccessToken(token("accueil"));await click();assert.equal(reads,1);await act(async()=>root.render(<RevenueRebookingReview institute="new" timezone="UTC"/>));assert.equal(document.querySelector("section"),null);
  }finally{await act(async()=>root.unmount());setAccessToken(token());}
});
