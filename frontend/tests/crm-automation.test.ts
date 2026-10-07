import test from "node:test";
import assert from "node:assert/strict";
import { automationTriggers,validAutomationOriginal,matchesAutomationReceipt,sameAutomationOriginal,type AutomationOriginal } from "../src/crm-automation-utils";
function original(): AutomationOriginal {
  return {id:"original",institute_id:"i",actor_id:"manager",created_at:"2026-10-07T00:00:00.000001Z",previous_policy_id:null,reason:"Explicit rules",idempotency_key:"key",
    policy:{institute_id:"i",rules:automationTriggers.map(trigger=>({trigger,enabled:false,offset_us:["rebooking","inactivity"].includes(trigger)?"1":"0"}))}};
}
test("six rules require exact explicit activation/duration and preserve large JSON microseconds",()=>{
  const r=original();r.policy.rules[4].offset_us="9007199254740993";assert.equal(validAutomationOriginal(r,"i"),true);
  for (const mutate of [(v: AutomationOriginal)=>v.policy.rules.pop(),(v: AutomationOriginal)=>v.policy.rules[5]=v.policy.rules[0],
    (v: AutomationOriginal)=>v.policy.rules[0].offset_us="1",(v: AutomationOriginal)=>v.policy.rules[2].offset_us="0",
    (v: AutomationOriginal)=>v.policy.rules[4].offset_us="253402300800000000",(v: AutomationOriginal)=>v.policy.rules[4].offset_us="01",(v: AutomationOriginal)=>v.policy.rules[4].offset_us="1\n",
    (v: AutomationOriginal)=>(v.policy.rules[4] as any).offset_us=9007199254740992,(v: AutomationOriginal)=>(v.policy.rules[0] as any).enabled="false",
    (v: AutomationOriginal)=>v.policy.institute_id="foreign",(v: AutomationOriginal)=>v.previous_policy_id=v.id]) {
    const v=original();mutate(v);assert.equal(validAutomationOriginal(v,"i"),false);
  }
});
test("recovery pins literal rule order, actor, predecessor, activation/duration and microsecond original clock",()=>{
  const a=original();assert.equal(matchesAutomationReceipt(a,a,"manager"),true);
  const alias=structuredClone(a);alias.created_at="2026-10-07T02:00:00.000001+02:00";assert.equal(sameAutomationOriginal(a,alias),true);
  for (const mutate of [(b: AutomationOriginal)=>b.policy.rules.reverse(),(b: AutomationOriginal)=>b.policy.rules[0].enabled=true,
    (b: AutomationOriginal)=>b.policy.rules[4].offset_us="1",(b: AutomationOriginal)=>b.actor_id="other",
    (b: AutomationOriginal)=>b.previous_policy_id="previous",(b: AutomationOriginal)=>b.created_at="2026-10-07T00:00:00.000002Z"]) {
    const b=structuredClone(a);mutate(b);assert.equal(sameAutomationOriginal(a,b),false);
  }
});
