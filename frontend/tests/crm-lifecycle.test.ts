import test from "node:test";
import assert from "node:assert/strict";
import { validLifecycleDeclaration,validLifecycleTerms,validLifecycleOriginal,matchesLifecycleReceipt,sameLifecycleOriginal,
  validBirthdayPolicy,validBirthdayPolicyOriginal,matchesBirthdayPolicyReceipt,sameBirthdayPolicyOriginal,validLifecycleRead,type LifecycleRead,type LifecycleOriginal,type BirthdayPolicyOriginal } from "../src/crm-lifecycle-utils";
function original(): LifecycleOriginal {
  return { id:"declaration",institute_id:"i",customer_id:"customer_a",actor_id:"manager",created_at:"2026-10-07T00:00:00Z",
    previous_id:null,reason:"Customer declaration",idempotency_key:"key",declaration:{institute_id:"i",customer_id:"customer_a",
      birthday:{month:2,day:29},birthday_evidence:"Customer stated month/day",communications:[
        {channel:"email",purpose:"service_follow_up",permission:"granted",evidence:"Explicit permission reference"},
        {channel:"email",purpose:"marketing",permission:"refused",evidence:"Explicit refusal reference"},
        {channel:"sms",purpose:"service_follow_up",permission:"unknown",evidence:null},
        {channel:"sms",purpose:"marketing",permission:"unknown",evidence:null}] } };
}
function calendar(): BirthdayPolicyOriginal {
  return { id:"calendar",institute_id:"i",actor_id:"manager",created_at:"2026-10-07T00:00:00Z",previous_policy_id:null,
    reason:"Explicit calendar",idempotency_key:"key",policy:{institute_id:"i",timezone:"Europe/Zurich",leap_day:"leap_year_only"} };
}
import { crmLifecycle as reading } from "./crm-lifecycle-fixture";
const validRead=(r: unknown)=>validLifecycleRead(r,"i","customer_a");
test("lifecycle declarations preserve explicit unknown, evidence, complete channels and valid leap birthday",()=>{
  assert.equal(validLifecycleOriginal(original(),"i","customer_a"),true);
  const unknown=original();unknown.declaration.birthday=null;unknown.declaration.birthday_evidence=null;
  assert.equal(validLifecycleDeclaration(unknown.declaration,"i","customer_a"),true);
  for(const mutate of [(r: LifecycleOriginal)=>{r.declaration.birthday!.day=30;},(r: LifecycleOriginal)=>{r.declaration.birthday_evidence=null;},
    (r: LifecycleOriginal)=>{r.declaration.communications.pop();},(r: LifecycleOriginal)=>{r.declaration.communications[1]=r.declaration.communications[0];},
    (r: LifecycleOriginal)=>{r.declaration.communications[0].evidence=null;},(r: LifecycleOriginal)=>{r.declaration.communications[2].evidence="Unproven";},
    (r: LifecycleOriginal)=>{r.customer_id="other";},(r: LifecycleOriginal)=>{r.previous_id=r.id;}]){
      const r=original();mutate(r);assert.equal(validLifecycleOriginal(r,"i","customer_a"),false);
  }
  const bad=original() as any;bad.declaration.birthday.month=true;assert.equal(validLifecycleOriginal(bad,"i","customer_a"),false);
  delete bad.previous_id;assert.equal(validLifecycleTerms(bad,"i","customer_a"),false);
});
test("lifecycle receipt pins purpose-specific evidence, actor, predecessor, scope and original clock",()=>{
  const a=original();assert.equal(matchesLifecycleReceipt(a,a,"manager"),true);assert.equal(matchesLifecycleReceipt(a,a,"other"),false);
  const alias=original();alias.created_at="2026-10-07T02:00:00+02:00";assert.equal(sameLifecycleOriginal(a,alias),true);
  alias.created_at="2026-10-07T00:00:00.000001Z";assert.equal(sameLifecycleOriginal(a,alias),false);
  for(const mutate of [(r: LifecycleOriginal)=>{r.declaration.communications[0].evidence="Different evidence";},
    (r: LifecycleOriginal)=>{r.declaration.communications[1].permission="granted";},(r: LifecycleOriginal)=>{r.previous_id="previous";},
    (r: LifecycleOriginal)=>{r.declaration.communications.reverse();},(r: LifecycleOriginal)=>{r.declaration.customer_id="other";}]){
    const r=original();mutate(r);assert.equal(matchesLifecycleReceipt(a,r,"manager"),false);
  }
  assert.equal(sameLifecycleOriginal({} as any,{} as any),false);
});
test("calendar original requires explicit named zone/leap rule and exact original recovery",()=>{
  const a=calendar();assert.equal(validBirthdayPolicyOriginal(a,"i"),true);assert.equal(matchesBirthdayPolicyReceipt(a,a,"manager"),true);
  const alias=calendar();alias.created_at="2026-10-07T02:00:00+02:00";assert.equal(sameBirthdayPolicyOriginal(a,alias),true);
  alias.created_at="2026-10-07T00:00:00.000001Z";assert.equal(sameBirthdayPolicyOriginal(a,alias),false);
  for(const zone of ["Unknown/Zone"," Europe/Zurich","+02:00",""]){const r=calendar();r.policy.timezone=zone;assert.equal(validBirthdayPolicy(r.policy,"i"),false);}
  for(const rule of ["february_28","march_1","leap_year_only"] as const){const r=calendar();r.policy.leap_day=rule;assert.equal(validBirthdayPolicy(r.policy,"i"),true);}
  const changed=calendar();changed.policy.timezone="UTC";assert.equal(matchesBirthdayPolicyReceipt(a,changed,"manager"),false);
  changed.policy=a.policy;changed.previous_policy_id="previous";assert.equal(matchesBirthdayPolicyReceipt(a,changed,"manager"),false);
  assert.equal(matchesBirthdayPolicyReceipt(a,a,"other"),false);assert.equal(validBirthdayPolicyOriginal(a,"foreign"),false);
  assert.equal(sameBirthdayPolicyOriginal({} as any,{} as any),false);
});
test("birthday reading independently checks local date, whole civil day and immutable source bindings",()=>{
  assert.equal(validRead(reading()),true);
  for(const mutate of [(r: LifecycleRead)=>{r.birthday!.due=false;},(r: LifecycleRead)=>{r.birthday!.local_date="2026-10-06";},
    (r: LifecycleRead)=>{r.birthday!.occurrence_end="2026-10-07T22:00:00.000001Z";},(r: LifecycleRead)=>{r.birthday!.declaration.communications[0].evidence="Changed evidence";},
    (r: LifecycleRead)=>{r.birthday!.capture.customer_id="foreign";},(r: LifecycleRead)=>{r.birthday!.customer.created_at="2020-01-01T00:00:00.000001Z";},
    (r: LifecycleRead)=>{r.birthday!.capture.captured_at="2026-10-07T00:00:00.000001Z";},(r: LifecycleRead)=>{(r.birthday as any).delivery_authorized=true;}]){
      const r=reading();mutate(r);assert.equal(validRead(r),false);
  }
  const alias=reading();alias.birthday!.occurrence_start="2026-10-07T00:00:00+02:00";assert.equal(validRead(alias),true);
  const notToday=reading();notToday.captured_at=notToday.birthday!.capture.captured_at="2026-10-06T00:00:00Z";
  notToday.birthday!.local_date="2026-10-06";notToday.birthday!.due=false;notToday.birthday!.reason="not_today";assert.equal(validRead(notToday),true);
});
test("DST and leap policy cannot become a guessed 24-hour day or default anniversary",()=>{
  for(const [month,day,capture,start,end] of [[3,29,"2026-03-29T12:00:00Z","2026-03-28T23:00:00Z","2026-03-29T22:00:00Z"],
    [10,25,"2026-10-25T12:00:00Z","2026-10-24T22:00:00Z","2026-10-25T23:00:00Z"]] as const){
    const r=reading();r.original!.declaration.birthday=r.birthday!.declaration.birthday={month,day};r.captured_at=r.birthday!.capture.captured_at=capture;
    r.birthday!.local_date=r.birthday!.anniversary_on=capture.slice(0,10);r.birthday!.occurrence_start=start;r.birthday!.occurrence_end=end;
    assert.equal(validRead(r),true);r.birthday!.occurrence_end=new Date(Date.parse(start)+86400000).toISOString();assert.equal(validRead(r),false);
  }
  const leap=reading();leap.original!.declaration.birthday=leap.birthday!.declaration.birthday={month:2,day:29};
  leap.captured_at=leap.birthday!.capture.captured_at="2026-02-28T12:00:00Z";leap.birthday!.local_date="2026-02-28";
  leap.birthday!.anniversary_on=leap.birthday!.occurrence_start=leap.birthday!.occurrence_end=null;leap.birthday!.due=false;leap.birthday!.reason="absent_in_calendar_year";
  assert.equal(validRead(leap),true);
  leap.calendar_original!.policy.leap_day=leap.birthday!.policy.leap_day="february_28";
  leap.birthday!.anniversary_on="2026-02-28";leap.birthday!.due=true;leap.birthday!.reason="birthday_today";
  leap.birthday!.occurrence_start="2026-02-27T23:00:00Z";leap.birthday!.occurrence_end="2026-02-28T23:00:00Z";assert.equal(validRead(leap),true);
  leap.calendar_original!.policy.leap_day=leap.birthday!.policy.leap_day="march_1";
  leap.birthday!.anniversary_on="2026-03-01";leap.birthday!.due=false;leap.birthday!.reason="not_today";
  leap.birthday!.occurrence_start="2026-02-28T23:00:00Z";leap.birthday!.occurrence_end="2026-03-01T23:00:00Z";assert.equal(validRead(leap),true);
});
test("unavailable source priority and unknown birthday preserve null observations/bounds",()=>{
  const absent=reading();absent.original=null;absent.unavailable_reason="declaration_absent";assert.equal(validRead(absent),false);
  absent.birthday=null;assert.equal(validRead(absent),true);absent.calendar_original=null;assert.equal(validRead(absent),true);
  const future=reading();future.original!.created_at="2026-10-07T00:00:00.000001Z";future.unavailable_reason="future_declaration";future.birthday=null;assert.equal(validRead(future),true);
  future.original!.created_at="2020-01-01T00:00:00Z";future.calendar_original!.created_at="2026-10-07T00:00:00.000001Z";future.unavailable_reason="future_calendar";assert.equal(validRead(future),true);
  future.calendar_original=null;future.unavailable_reason="calendar_absent";assert.equal(validRead(future),true);
  future.calendar_original=calendar();future.calendar_original.created_at="2020-01-01T00:00:00Z";future.customer.created_at="2026-10-07T00:00:00.000001Z";
  future.unavailable_reason="future_registration";assert.equal(validRead(future),true);
  const unknown=reading();unknown.original!.declaration.birthday=unknown.birthday!.declaration.birthday=null;
  unknown.original!.declaration.birthday_evidence=unknown.birthday!.declaration.birthday_evidence=null;unknown.birthday!.anniversary_on=null;
  unknown.birthday!.occurrence_start=unknown.birthday!.occurrence_end=null;unknown.birthday!.due=false;unknown.birthday!.reason="birthday_unknown";assert.equal(validRead(unknown),true);
});
