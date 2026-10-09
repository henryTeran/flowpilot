import test from "node:test";
import assert from "node:assert/strict";
import {validReturnOpportunities} from "../src/copilot-return-opportunity-utils";
const capture="2026-10-09T12:00:00.123456Z";
const candidate={institute_id:"own",customer_id:"customer",policy_original_id:"policy",rule:{trigger:"rebooking",enabled:true,offset_us:"1"},source:{institute_id:"own",customer_id:"customer",source_id:"care",source_kind:"care_episode",occurred_at:"2026-10-09T12:00:00.123455Z",expires_at:null,remaining:null},due_at:capture,valid_until:null,captured_at:capture,state:"due",external_message_sent:false,delivery_authorized:false};
const source={institute_id:"own",captured_at:capture,source_digest:"a".repeat(64),source:"observed_care_declared_rebooking_rule",total_candidates:1,examined_customers:2,already_booked_customers:1,scheduled_customers:0,disabled_customers:0,no_candidate_customers:0,diagnostics:{},candidates:[candidate],page_limit:20,estimated_value:null,delivery_authorized:false,action_executed:false,complete_customer_history:false};
test("return opportunities retain due original care, cohort partition and no delivery authority",()=>{
  const valid=(v:unknown)=>validReturnOpportunities(v,"own",capture);assert.ok(valid(source));
  for(const change of [{delivery_authorized:true},{estimated_value:"100"},{examined_customers:3},{diagnostics:{birthday_unavailable:1}},{candidates:[{...candidate,customer_id:"foreign"}]},{candidates:[{...candidate,state:"scheduled"}]},{candidates:[{...candidate,phone:"private"}]},{candidates:[{...candidate,due_at:"2026-10-09T12:00:00.123455Z"}]}])assert.equal(valid({...source,...change}),false);
});
