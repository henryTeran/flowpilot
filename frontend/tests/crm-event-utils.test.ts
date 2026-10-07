import test from "node:test";
import assert from "node:assert/strict";
import { validEventCandidate, eventIdentity, validEventDecision, validEventRevision, validEventPage, validEventRequest, validEventSource, validEventCapture, matchesEventCapture, type EventSource, type EventCandidate } from "../src/crm-event-utils";
const candidate:EventCandidate={institute_id:"i",customer_id:"c",policy_original_id:"p",rule:{trigger:"post_service",enabled:true,offset_us:"1"},source:{institute_id:"i",customer_id:"c",source_id:"ticket",source_kind:"care_episode",occurred_at:"2026-10-07T12:00:00Z",expires_at:null,remaining:null},due_at:"2026-10-07T12:00:00.000001Z",valid_until:null,captured_at:"2026-10-07T12:00:00Z",state:"scheduled",delivery_authorized:false,external_message_sent:false};
test("event candidate recomputes exact timing and state; refuses forged ownership, source and delivery",()=>{
 assert.equal(validEventCandidate(candidate,"i","c"),true);
 for(const patch of [{state:"due"},{due_at:"2026-10-07T12:00:00Z"},{delivery_authorized:true},{external_message_sent:true},{valid_until:"2026-10-08T12:00:00Z"},{source:{...candidate.source,customer_id:"foreign"}},{rule:{...candidate.rule,offset_us:1}}])assert.equal(validEventCandidate({...candidate,...patch},"i","c"),false);
 assert.equal(validEventCandidate({...candidate,captured_at:candidate.due_at,state:"due"},"i","c"),true);
 assert.equal(validEventCandidate({...candidate,rule:{...candidate.rule,enabled:false},state:"disabled"},"i","c"),true);
});
test("expiry anticipation clamps to issue; package exhaustion and disabled precedence are explicit",()=>{
 const p:EventCandidate={...candidate,rule:{trigger:"package_expiry",enabled:true,offset_us:"9007199254740993"},source:{...candidate.source,source_kind:"package",expires_at:"2026-10-08T12:00:00Z",remaining:1},due_at:candidate.source.occurred_at,valid_until:"2026-10-08T12:00:00Z",state:"due"};
 assert.equal(validEventCandidate(p,"i","c"),true);
 const exhausted={...p,source:{...p.source,remaining:0},state:"exhausted"};assert.equal(validEventCandidate(exhausted,"i","c"),true);
 assert.equal(validEventCandidate({...exhausted,state:"due"},"i","c"),false);
 assert.equal(validEventCandidate({...p,captured_at:p.valid_until,state:"expired"},"i","c"),true);
 assert.equal(validEventCandidate({...exhausted,rule:{...p.rule,enabled:false},state:"disabled"},"i","c"),true);
});

test("care recency, local birthday interval and membership expiry retain distinct source semantics",()=>{
 for(const trigger of ["rebooking","inactivity"] as const)assert.equal(validEventCandidate({...candidate,rule:{...candidate.rule,trigger}},"i","c"),true);
 const birthday:EventCandidate={...candidate,rule:{trigger:"birthday",enabled:true,offset_us:"0"},source:{...candidate.source,source_kind:"birthday",source_id:"2026-10-08",occurred_at:"2026-10-07T22:00:00Z",expires_at:"2026-10-08T22:00:00Z"},due_at:"2026-10-07T22:00:00Z",valid_until:"2026-10-08T22:00:00Z"};
 assert.equal(validEventCandidate(birthday,"i","c"),true);
 assert.equal(validEventCandidate({...birthday,rule:{...birthday.rule,offset_us:"1"}},"i","c"),false);
 const membership:EventCandidate={...candidate,rule:{trigger:"subscription_renewal",enabled:true,offset_us:"1"},source:{...candidate.source,source_kind:"membership",expires_at:"2026-10-08T12:00:00Z"},due_at:"2026-10-08T11:59:59.999999Z",valid_until:"2026-10-08T12:00:00Z"};
 assert.equal(validEventCandidate(membership,"i","c"),true);
 assert.equal(validEventCandidate({...membership,source:{...membership.source,remaining:1}},"i","c"),false);
});

test("occurrence identity matches Python ASCII/UTC canonical hashing and keeps renewed terms distinct",async()=>{
 assert.equal(await eventIdentity(candidate),"6595be3e2da43ac29cc0d3ce6e2216bea4f4a91d8a2857ec8863dede15f0a234");
 const term={...candidate,rule:{...candidate.rule,trigger:"package_expiry" as const},source:{...candidate.source,source_kind:"package" as const,source_id:"caf\u00e9\ud83d\ude00",expires_at:"2026-10-08T14:00:00.000001+02:00"}};
 assert.equal(await eventIdentity(term),"b5e77d9b3824672011ef34657df54e51ddb6ca55a9e8e3d0bb5432690e06a518");
 assert.equal(await eventIdentity({...term,source:{...term.source,expires_at:"2026-10-08T12:00:00.000001Z"}}),await eventIdentity(term));
 assert.notEqual(await eventIdentity({...term,source:{...term.source,expires_at:"2026-10-08T12:00:00.000002Z"}}),await eventIdentity(term));
});
test("revision and bounded current page refuse changed occurrence, scope, predecessor, clock, state and total",async()=>{
 const key=await eventIdentity(candidate),decision={event_key:key,candidate,state:"scheduled" as const,reason:"candidate" as const,evaluated_at:candidate.captured_at};
 const revision={id:"r",institute_id:"i",customer_id:"c",event_key:key,capture_id:"capture",previous_id:null,decision};
 assert.equal(await validEventRevision(revision,"i","c"),true);
 for(const patch of [{event_key:"forged"},{previous_id:"r"},{customer_id:"foreign"},{decision:{...decision,state:"due"}},{decision:{...decision,evaluated_at:"2026-10-07T11:59:59.999999Z"}}])assert.equal(await validEventRevision({...revision,...patch},"i","c"),false);
 assert.equal(await validEventDecision({...decision,state:"processed",reason:"already_processed"},"i","c"),true);
 const page={institute_id:"i",customer_id:"c",total:1,offset:0,limit:20,revisions:[revision]};
 assert.equal(await validEventPage(page,"i","c",0,20),true);
 for(const patch of [{total:2},{offset:1},{limit:50},{revisions:[revision,revision]}])assert.equal(await validEventPage({...page,...patch},"i","c",0,20),false);
 assert.equal(await validEventPage({...page,total:0,revisions:[]},"i","c",0,20),true);
});

function sourceFixture():EventSource {
 const customer={institute_id:"i",customer_id:"c",created_at:"2020-01-01T00:00:00Z"};
 return {institute_id:"i",customer_id:"c",captured_at:candidate.captured_at,customer,policy_original:null,lifecycle:{institute_id:"i",customer_id:"c",captured_at:candidate.captured_at,customer,original:null,calendar_original:null,birthday:null,unavailable_reason:"declaration_absent",delivery_authorized:false,external_message_sent:false},anchors:[candidate.source],candidates:[],diagnostics:{policy_absent:1,future_policy:0,future_registration:0,birthday_unavailable:1,care_unavailable:0,care_unlinked_ticket:0,care_invalid_owner_or_service:0,care_invalid_actual_times:0,invalid_event_timing:0,package_absent:1,membership_absent:1,invalid_package:0,invalid_membership:0},complete_customer_history:false,delivery_authorized:false,external_message_sent:false};
}
test("source capture pins lifecycle clock, complete diagnostics and explicit policy before candidate eligibility",()=>{
 const source=sourceFixture();assert.equal(validEventSource(source,"i","c"),true);
 for(const patch of [{candidates:[candidate]},{diagnostics:{...source.diagnostics,policy_absent:0}},{lifecycle:{...source.lifecycle,captured_at:"2026-10-07T12:00:00.000001Z"}},{anchors:[candidate.source,candidate.source]},{complete_customer_history:true}])assert.equal(validEventSource({...source,...patch},"i","c"),false);
});
test("event action receipt verifies actor and literal target terms; retained older revisions are allowed",async()=>{
 const source=sourceFixture(),terms={action:"reconcile" as const,event_key:null,expected_revision_id:null,reason:"Explicit reconciliation",idempotency_key:"key"};
 const decision={event_key:await eventIdentity(candidate),candidate,state:"scheduled" as const,reason:"candidate" as const,evaluated_at:candidate.captured_at};
 const r={id:"r",institute_id:"i",customer_id:"c",event_key:decision.event_key,capture_id:"older",previous_id:null,decision};
 const receipt={id:"capture",institute_id:"i",customer_id:"c",actor_id:"manager",request:terms,captured_at:source.captured_at,source,revisions:[r]};
 assert.equal(await validEventCapture(receipt,"i","c"),true);assert.equal(await matchesEventCapture(receipt,"i","c",terms,"manager"),true);
 assert.equal(await matchesEventCapture(receipt,"i","c",terms,"foreign"),false);
 assert.equal(await matchesEventCapture(receipt,"i","c",{...terms,reason:"Changed reason"},"manager"),false);
 assert.equal(await validEventCapture({...receipt,revisions:[r,r]},"i","c"),false);
 assert.equal(await validEventCapture({...receipt,request:{...terms,action:"process",event_key:decision.event_key,expected_revision_id:r.id}},"i","c"),false);
 assert.equal(await validEventCapture({...receipt,captured_at:"2026-10-07T12:00:00.000001Z"},"i","c"),false);
 assert.equal(validEventRequest({...terms,action:"cancel"}),false);
 assert.equal(validEventRequest({...terms,action:"cancel",event_key:decision.event_key,expected_revision_id:r.id}),true);
});

test("eligible source capture requires every policy-derived care occurrence, exact rule and source",()=>{
 const s=sourceFixture();s.policy_original={id:"p",institute_id:"i",actor_id:"manager",created_at:"2020-01-01T00:00:00Z",previous_policy_id:null,reason:"Explicit rules",idempotency_key:"p",policy:{institute_id:"i",rules:[{trigger:"birthday",enabled:false,offset_us:"0"},{trigger:"post_service",enabled:true,offset_us:"1"},{trigger:"rebooking",enabled:true,offset_us:"1"},{trigger:"inactivity",enabled:true,offset_us:"1"},{trigger:"package_expiry",enabled:false,offset_us:"0"},{trigger:"subscription_renewal",enabled:false,offset_us:"0"}]}};
 s.diagnostics.policy_absent=0;s.candidates=[candidate,{...candidate,rule:{...candidate.rule,trigger:"rebooking"}},{...candidate,rule:{...candidate.rule,trigger:"inactivity"}}];
 assert.equal(validEventSource(s,"i","c"),true);
 assert.equal(validEventSource({...s,candidates:s.candidates.slice(1)},"i","c"),false);
 assert.equal(validEventSource({...s,candidates:[candidate,candidate,s.candidates[2]]},"i","c"),false);
 assert.equal(validEventSource({...s,candidates:s.candidates.map(c=>({...c,policy_original_id:"foreign"}))},"i","c"),false);
 assert.equal(validEventSource({...s,diagnostics:{...s.diagnostics,care_invalid_actual_times:1}},"i","c"),false);
});
