import type { LifecycleRead,LifecycleOriginal,BirthdayPolicyOriginal } from "../src/crm-lifecycle-utils";
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
export function crmLifecycle(): LifecycleRead {
  const o=original(),c=calendar();o.created_at=c.created_at="2020-01-01T00:00:00Z";o.declaration.birthday={month:10,day:7};
  const customer={institute_id:"i",customer_id:"customer_a",created_at:"2020-01-01T00:00:00Z"};
  return {institute_id:"i",customer_id:"customer_a",captured_at:"2026-10-07T00:00:00Z",customer,original:o,calendar_original:c,
    unavailable_reason:null,delivery_authorized:false,external_message_sent:false,birthday:{basis:"declared_birthday_local_calendar",
      declaration:structuredClone(o.declaration),policy:structuredClone(c.policy),customer:{...customer},capture:{institute_id:"i",customer_id:"customer_a",captured_at:"2026-10-07T00:00:00Z"},
      local_date:"2026-10-07",anniversary_on:"2026-10-07",due:true,reason:"birthday_today",occurrence_start:"2026-10-06T22:00:00Z",occurrence_end:"2026-10-07T22:00:00Z",delivery_authorized:false,external_message_sent:false} };
}
