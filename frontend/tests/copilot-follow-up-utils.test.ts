import test from "node:test";
import assert from "node:assert/strict";
import {validFollowUps} from "../src/copilot-follow-up-utils";
const capture="2026-10-09T12:00:00.123456Z",period={start:"2026-10-08T00:00:00Z",end:"2026-10-09T00:00:00Z"},window={institute_id:"own",...period,captured_at:capture};
const event={event_id:"event",appointment_id:"booking",type:"review_cancelled_booking",occurred_at:period.start,estimated_value:null};
const source={institute_id:"own",captured_at:capture,source:"recorded_closure_follow_up",bookings:{window,source_digest:"a".repeat(64),cancelled_count:1,no_show_count:0,unpriced_count:1,institute_terminal_bookings_without_closure_event:0},walk_ins:{window,source_digest:"b".repeat(64),retained_terms_count:0,legacy_unpriced_count:1,retained_amounts:[]},booking_total:1,walk_in_total:1,booking_candidates:[event],walk_in_candidates:[{event_id:1,ticket_id:"ticket",type:"review_cancelled_walk_in",occurred_at:period.start,retained_value:null,confidence:"legacy_cancellation_unpriced"}],page_limit_per_source:20,estimated_recovered_revenue:null,causal_loss_proven:false,delivery_authorized:false,action_executed:false,complete_history:false};
test("follow-ups retain original source totals, exclusive period and unavailable recovery",()=>{
  const valid=(v:unknown)=>validFollowUps(v,"own",period,capture);assert.ok(valid(source));
  for(const change of [{delivery_authorized:true},{estimated_recovered_revenue:"100"},{booking_total:2},{booking_candidates:[{...event,occurred_at:period.end}]},{booking_candidates:[{...event,phone:"private"}]},{walk_in_candidates:[{...source.walk_in_candidates[0],retained_value:{currency:"CHF",amount_minor:"100",basis:"recorded_cancelled_commercial_value"}}]},{walk_ins:{...source.walk_ins,window:{...window,institute_id:"foreign"}}}])assert.equal(valid({...source,...change}),false);
});
