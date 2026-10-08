import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { validRevenueRebooking } from "../src/revenue-rebooking-utils";
const vector=JSON.parse(readFileSync(new URL("./fixtures/revenue-rebooking-14v.json",import.meta.url),"utf8"));
test("rebooking review binds original rule, observed-care chronology, partition and permission provenance",()=>{
  assert.equal(validRevenueRebooking(vector,"own",0),true);
  for(const mutate of [
    (r:any)=>{r.delivery_authorized=0;},(r:any)=>{r.external_message_sent=true;},(r:any)=>{r.complete_customer_history=true;},
    (r:any)=>{r.examined_customers=6;},(r:any)=>{r.page.limit=50;},(r:any)=>{r.diagnostics.unrelated=0;},(r:any)=>{r.diagnostics.care_unavailable=3;},(r:any)=>{r.opportunities[1].evidence.customer_id="customer-0";},
    (r:any)=>{r.opportunities[0].estimated_value="0";},(r:any)=>{r.opportunities[0].action_executed=true;},(r:any)=>{r.opportunities[0].candidate.due_at="2026-01-03T12:00:00.000001Z";},
    (r:any)=>{r.opportunities[0].candidate.source.source_kind="birthday";},(r:any)=>{r.opportunities[0].candidate.delivery_authorized=true;},
    (r:any)=>{r.opportunities[0].evidence.policy_original.policy.rules.find((x:any)=>x.trigger==="rebooking").offset_us="86400000001";},
    (r:any)=>{r.opportunities[1].evidence.policy_original.actor_id="different-manager";},(r:any)=>{r.opportunities[0].evidence.policy_original.created_at="2026-01-06T00:00:00Z";},
    (r:any)=>{r.opportunities[0].evidence.customer.created_at="2026-01-03T00:00:00Z";},(r:any)=>{r.opportunities[0].evidence.captured_at="2026-01-05T00:00:01Z";},
    (r:any)=>{r.opportunities[0].evidence.diagnostics.care_unlinked_ticket=1;},(r:any)=>{r.opportunities[0].evidence.lifecycle_unavailable_reason=null;},
    (r:any)=>{r.opportunities[1].evidence.lifecycle_original.declaration.customer_id="foreign";},(r:any)=>{r.opportunities[1].evidence.lifecycle_original.declaration.communications[0].evidence=null;},
    (r:any)=>{r.opportunities[1].evidence.lifecycle_original.created_at="2026-01-06T00:00:00Z";r.opportunities[1].evidence.lifecycle_unavailable_reason=null;},
  ]) { const r=structuredClone(vector);mutate(r);assert.equal(validRevenueRebooking(r,"own",0),false); }
  const future=structuredClone(vector);future.opportunities[1].evidence.lifecycle_original.created_at="2026-01-06T00:00:00Z";future.opportunities[1].evidence.lifecycle_unavailable_reason="calendar_absent";
  assert.equal(validRevenueRebooking(future,"own",0),true);future.opportunities[1].evidence.lifecycle_unavailable_reason="future_declaration";assert.equal(validRevenueRebooking(future,"own",0),true);
});
test("customer pages preserve whole catalog partition and reject duplicate/order/short pages and unsafe counts",()=>{
  const r=structuredClone(vector),rows=[];for(let n=0;n<25;n++){const o=structuredClone(vector.opportunities[0]),id=`customer-${String(n).padStart(2,"0")}`;o.evidence.customer_id=o.evidence.customer.customer_id=o.candidate.customer_id=o.candidate.source.customer_id=id;rows.push(o);}
  r.page.total=25;r.examined_customers=30;r.opportunities=rows.slice(0,20);assert.equal(validRevenueRebooking(r,"own",0),true);
  r.page.offset=20;r.opportunities=rows.slice(20);assert.equal(validRevenueRebooking(r,"own",20),true);r.opportunities.pop();assert.equal(validRevenueRebooking(r,"own",20),false);
  const empty={...vector,page:{offset:0,limit:20,total:0},opportunities:[],examined_customers:0,already_booked_customers:0,scheduled_customers:0,disabled_customers:0,no_candidate_customers:0,diagnostics:{}};
  assert.equal(validRevenueRebooking(empty,"own",0),true);assert.equal(validRevenueRebooking(empty,"own",-1),false);
  empty.examined_customers=Number.MAX_SAFE_INTEGER+1;assert.equal(validRevenueRebooking(empty,"own",0),false);
});
