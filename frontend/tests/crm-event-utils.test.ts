import test from "node:test";
import assert from "node:assert/strict";
import { validEventCandidate, eventIdentity, validEventDecision, validEventRevision, validEventPage, type EventCandidate } from "../src/crm-event-utils";
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
