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
