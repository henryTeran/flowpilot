import test from "node:test";
import assert from "node:assert/strict";
import {validLossRead} from "../src/copilot-loss-utils";
const capture="2026-10-09T12:00:00.123456Z",period={start:"2026-10-08T00:00:00Z",end:"2026-10-09T00:00:00Z"};
const window={institute_id:"own",...period,captured_at:capture};
const source={institute_id:"own",captured_at:capture,bookings:{window,source_digest:"a".repeat(64),cancelled_count:2,no_show_count:1,unpriced_count:3,institute_terminal_bookings_without_closure_event:1},walk_ins:{window,source_digest:"b".repeat(64),retained_terms_count:0,legacy_unpriced_count:1,retained_amounts:[]},causal_loss_proven:false,complete_history:false,financial_loss:null,basis:"recorded_closure_events_not_causal_financial_loss"};
test("loss summary preserves independent clocks, unpriced events and unknown causal loss",()=>{
  const valid=(v:unknown)=>validLossRead(v,"own",period,capture);
  assert.ok(valid(source));assert.ok(valid({...source,bookings:{...source.bookings,window:{...window,captured_at:"2026-10-09T12:00:00.123455Z"}}}));
  for(const change of [{financial_loss:"100"},{causal_loss_proven:true},{complete_history:true},{institute_id:"foreign"},{phone:"private"},{bookings:{...source.bookings,unpriced_count:2}},{walk_ins:{...source.walk_ins,retained_terms_count:1}},{bookings:{...source.bookings,window:{...window,end:capture}}}])assert.equal(valid({...source,...change}),false);
});
