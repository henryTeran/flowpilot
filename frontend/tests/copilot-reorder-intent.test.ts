import test from "node:test";
import assert from "node:assert/strict";
import {revenueOriginalFingerprint as hash} from "../src/revenue-scenario-utils";
import {validReorderPreview,validReorderSelection,validReorderReceipt,type ReorderRequest} from "../src/copilot-reorder-utils";

import {createReorderIntent} from "../src/copilot-reorder-intent";
async function fixture(){
  const selection:ReorderRequest["selection"]={supplier_id:"supplier",item_ids:["item"],pending_order_assumption:"ignore_pending_orders",scenario:null};
  const raw={institute_id:"own",selection,coverage:"not_applicable",items:[{item_id:"item",unit:"unit",on_hand:"1.000",threshold:"4.000",pending_order_quantity:"2.000",known_demand:"0.000",complete_demand:null,proposed_quantity:"3.000"}],source_digest:"a".repeat(64),basis:"original_stock_shortfalls_selected_scenario_and_explicit_pending_assumption_not_supplier_quote",effect:"reorder_proposal_only_no_order_contact_payment_receipt_or_stock_write"};
  const preview={...raw,captured_at:"2026-10-09T12:00:00.123456Z",state_fingerprint:await hash(raw)},request:ReorderRequest={selection,expected_state_fingerprint:preview.state_fingerprint,reason:"Proposition relue",idempotency_key:"proposal-key"};
  const original={...request,id:"proposal",institute_id:"own",actor_id:"manager",created_at:"2026-10-09T12:00:00.123457Z",preview};return {request,receipt:{original,fingerprint:await hash(original)}};}
test("lost proposal response resumes without duplicate and independently rereads ID",async()=>{
const f=await fixture(),values=new Map<string,string>(),storage={getItem:(k:string)=>values.get(k)??null,setItem:(k:string,v:string)=>{values.set(k,v);},removeItem:(k:string)=>{values.delete(k);}};let retained:unknown=null,writes=0;const paths:string[]=[];
const options={institute:"own",actor:"manager",storage,current:()=>true,get:async(p:string)=>{paths.push(p);return p.includes("by-key") ? retained : f.receipt;},post:async(p:string,b:unknown)=>{assert.equal(p,"/copilot/prepare/reorder");writes++;retained=f.receipt;throw Error("Lost response");}};
const driver=createReorderIntent(options);await assert.rejects(driver.submit({message:"Preparer une proposition de reapprovisionnement",proposal:f.request}));assert.equal(driver.state().status,"frozen");const reload=createReorderIntent(options);assert.equal((await reload.submit()).status,"confirmed");assert.equal(writes,1);assert.equal(reload.state().status,"empty");assert.ok(paths.includes("/copilot/reorder-proposals/proposal"));
});
test("proposal receipt damage and ambiguous failure preserve frozen request; definitive rejection needs fresh absence",async()=>{
  const f=await fixture(),makeStorage=()=>{const m=new Map<string,string>();return {getItem:(k:string)=>m.get(k)??null,setItem:(k:string,v:string)=>{m.set(k,v);},removeItem:(k:string)=>{m.delete(k);}};};
  for(const status of [400,500]){let reads=0;const d=createReorderIntent({institute:"own",actor:"manager",storage:makeStorage(),current:()=>true,get:async()=>{reads++;return null;},post:async()=>{throw Object.assign(Error("Rejected"),{status});}});await assert.rejects(d.submit({message:"Explicit proposal",proposal:f.request}));assert.equal(d.canCorrect(),status===400);if(status===400){assert.equal((await d.correct()).status,"correctable");assert.equal(reads,2);assert.equal(d.state().status,"empty");}else{await assert.rejects(d.correct());assert.equal(d.state().status,"frozen");}}
  const wrong={...f.receipt.original,id:"another-original"},damaged={original:wrong,fingerprint:await hash(wrong)};let writes=0;
  const d=createReorderIntent({institute:"own",actor:"manager",storage:makeStorage(),current:()=>true,get:async p=>p.includes("by-key") ? f.receipt : damaged,post:async()=>{writes++;return f.receipt;}});await assert.rejects(d.submit({message:"Explicit proposal",proposal:f.request}));assert.equal(writes,0);assert.equal(d.state().status,"frozen");
});
test("proposal corrupt storage and session change during concurrent recovery block all writes",async()=>{
  const f=await fixture(),m=new Map<string,string>(),storage={getItem:(k:string)=>m.get(k)??null,setItem:(k:string,v:string)=>{m.set(k,v);},removeItem:(k:string)=>{m.delete(k);}};let live=true,writes=0,release:(v:unknown)=>void=()=>{};
  const options={institute:"own",actor:"manager",storage,current:()=>live,get:async()=>new Promise(resolve=>{release=resolve;}),post:async()=>{writes++;return f.receipt;}};const first=createReorderIntent(options),second=createReorderIntent(options),pending=first.submit({message:"Explicit proposal",proposal:f.request});assert.equal((await second.submit()).status,"busy");live=false;release(null);assert.equal((await pending).status,"stale");assert.equal(writes,0);assert.equal(first.state().status,"frozen");
  for(const k of m.keys())m.set(k,"corrupt");live=true;const broken=createReorderIntent(options);await assert.rejects(broken.submit({message:"Replacement",proposal:f.request}));assert.equal(broken.state().status,"invalid");assert.equal(writes,0);
});
