import test from "node:test";
import assert from "node:assert/strict";
import {revenueOriginalFingerprint as hash} from "../src/revenue-scenario-utils";
import {validReorderPreview,validReorderSelection} from "../src/copilot-reorder-utils";
test("reorder projection binds explicit assumption, source digest and exact stock arithmetic",async()=>{
  const selection={supplier_id:"supplier",item_ids:["item"],pending_order_assumption:"ignore_pending_orders",scenario:null};
  const raw={institute_id:"own",selection,coverage:"not_applicable",items:[{item_id:"item",unit:"ml",on_hand:"1.250",threshold:"5.000",pending_order_quantity:"2.000",known_demand:"0.000",complete_demand:null,proposed_quantity:"3.750"}],source_digest:"a".repeat(64),basis:"original_stock_shortfalls_selected_scenario_and_explicit_pending_assumption_not_supplier_quote",effect:"reorder_proposal_only_no_order_contact_payment_receipt_or_stock_write"};
  const seal=async(r:any)=>({...r,captured_at:"2026-10-09T12:00:00Z",state_fingerprint:await hash(r)});assert.ok(await validReorderPreview(await seal(raw),"own"));
  const conditional={...raw,selection:{...selection,pending_order_assumption:"all_pending_orders_received"},items:[{...raw.items[0],proposed_quantity:"1.750"}]};assert.ok(await validReorderPreview(await seal(conditional),"own"));
  for(const change of [{items:[{...raw.items[0],proposed_quantity:"4.000"}]},{coverage:"complete_selected_norms"},{items:[{...raw.items[0],complete_demand:"0.000"}]},{items:[{...raw.items[0],unit:"unit"}]},{effect:"purchase_order_created"}])assert.equal(await validReorderPreview(await seal({...raw,...change}),"own"),false);
  assert.equal(await validReorderPreview(await seal(raw),"foreign"),false);assert.equal(validReorderSelection({...selection,item_ids:["item","item"]}),false);assert.equal(validReorderSelection({...selection,automatic_purchase:true}),false);
});
