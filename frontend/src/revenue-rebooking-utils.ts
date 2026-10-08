import { certificationInstant as instant } from "./certification-utils";
import { validEventCandidate, type EventCandidate } from "./crm-event-utils";
import { validAutomationOriginal, sameAutomationOriginal, type AutomationOriginal } from "./crm-automation-utils";
import { validLifecycleOriginal, type LifecycleOriginal } from "./crm-lifecycle-utils";
export const rebookingDiagnostics = ["policy_absent", "future_policy", "future_registration", "invalid_event_timing", "care_unavailable", "care_unlinked_ticket", "care_invalid_owner_or_service", "care_invalid_actual_times"] as const;
type Diagnostics = Record<typeof rebookingDiagnostics[number], number>;
export type RebookingOpportunity = { type: "review_due_rebooking";
  evidence: { institute_id: string; customer_id: string; captured_at: string; customer: { institute_id: string; customer_id: string; created_at: string };
    policy_original: AutomationOriginal; lifecycle_original: LifecycleOriginal | null;
    lifecycle_unavailable_reason: "declaration_absent" | "calendar_absent" | "future_declaration" | "future_calendar" | null; diagnostics: Diagnostics };
  candidate: EventCandidate; estimated_value: null; confidence: "observed_care_and_declared_rule_only";
  recommended_action: "review_return_need_contact_permission_and_feasible_slot"; action_executed: false };
export type RevenueRebooking = { institute_id: string; captured_at: string; basis: "latest_observed_care_and_current_declared_rebooking_rule";
  page: { offset: number; limit: number; total: number }; opportunities: RebookingOpportunity[]; examined_customers: number; already_booked_customers: number;
  scheduled_customers: number; disabled_customers: number; no_candidate_customers: number; diagnostics: Partial<Diagnostics>;
  complete_customer_history: false; delivery_authorized: false; external_message_sent: false };
const keys = (v: unknown, names: string): v is Record<string, unknown> => !!v && typeof v === "object" && !Array.isArray(v)
  && Object.keys(v).sort().join(" ") === names.split(" ").sort().join(" ");
const count = (v: unknown): v is number => typeof v === "number" && Number.isSafeInteger(v) && v >= 0;
const id = (v: unknown): v is string => typeof v === "string" && !!v && v.trim() === v && Array.from(v).length <= 80;
function ordered(a: string,b: string) { const x=Array.from(a),y=Array.from(b); for(let n=0;n<Math.min(x.length,y.length);n++) { const d=x[n].codePointAt(0)!-y[n].codePointAt(0)!; if(d) return d<0; } return x.length<y.length; }
function policy(v: unknown,institute: string): v is AutomationOriginal {
  return keys(v,"policy previous_policy_id reason idempotency_key id institute_id actor_id created_at") && keys(v.policy,"institute_id rules")
    && Array.isArray(v.policy.rules) && v.policy.rules.every(r=>keys(r,"trigger enabled offset_us")) && validAutomationOriginal(v,institute);
}
function lifecycle(v: unknown,institute: string,customer: string): v is LifecycleOriginal {
  return keys(v,"declaration previous_id reason idempotency_key id institute_id customer_id actor_id created_at")
    && keys(v.declaration,"institute_id customer_id birthday birthday_evidence communications")
    && (v.declaration.birthday===null || keys(v.declaration.birthday,"month day")) && Array.isArray(v.declaration.communications)
    && v.declaration.communications.every(c=>keys(c,"channel purpose permission evidence")) && validLifecycleOriginal(v,institute,customer);
}
export function validRevenueRebooking(v: unknown,institute: string,offset: number): v is RevenueRebooking {
  if(!count(offset) || !keys(v,"institute_id captured_at basis page opportunities examined_customers already_booked_customers scheduled_customers disabled_customers no_candidate_customers diagnostics complete_customer_history delivery_authorized external_message_sent")
    || v.institute_id!==institute || v.basis!=="latest_observed_care_and_current_declared_rebooking_rule" || v.complete_customer_history!==false || v.delivery_authorized!==false || v.external_message_sent!==false
    || !keys(v.page,"offset limit total") || v.page.offset!==offset || v.page.limit!==20 || !count(v.page.total)
    || ![v.examined_customers,v.already_booked_customers,v.scheduled_customers,v.disabled_customers,v.no_candidate_customers].every(count)
    || !Array.isArray(v.opportunities) || v.opportunities.length!==Math.min(20,Math.max(0,v.page.total-offset))) return false;
  const capture=instant(v.captured_at); if(capture===undefined) return false;
  if([v.page.total,v.already_booked_customers,v.scheduled_customers,v.disabled_customers,v.no_candidate_customers].reduce<bigint>((sum,n)=>sum+BigInt(n as number),0n)!==BigInt(v.examined_customers as number)
    || !keys(v.diagnostics,(v.examined_customers as number)>0 ? rebookingDiagnostics.join(" ") : "") || !Object.values(v.diagnostics).every(count)) return false;
  if((v.examined_customers as number)>0 && (["policy_absent","future_policy","future_registration","invalid_event_timing","care_unavailable"].some(k=>(v.diagnostics as Record<string,number>)[k]>(v.no_candidate_customers as number))
    || v.no_candidate_customers===0 && Object.values(v.diagnostics).some(n=>n!==0))) return false;
  let previous: string|undefined, firstPolicy: AutomationOriginal|undefined;
  for(const o of v.opportunities) {
    if(!keys(o,"type evidence candidate estimated_value confidence recommended_action action_executed") || o.type!=="review_due_rebooking" || o.estimated_value!==null
      || o.confidence!=="observed_care_and_declared_rule_only" || o.recommended_action!=="review_return_need_contact_permission_and_feasible_slot" || o.action_executed!==false
      || !keys(o.evidence,"institute_id customer_id captured_at customer policy_original lifecycle_original lifecycle_unavailable_reason diagnostics")) return false;
    const e=o.evidence, customer=e.customer_id;
    if(e.institute_id!==institute || !id(customer) || previous!==undefined && !ordered(previous,customer) || instant(e.captured_at)!==capture
      || !keys(e.customer,"institute_id customer_id created_at") || e.customer.institute_id!==institute || e.customer.customer_id!==customer
      || instant(e.customer.created_at)===undefined || instant(e.customer.created_at)!>capture || !policy(e.policy_original,institute) || instant(e.policy_original.created_at)!>capture
      || !keys(e.diagnostics,rebookingDiagnostics.join(" ")) || !Object.values(e.diagnostics).every(n=>n===0)) return false;
    previous=customer;
    if(firstPolicy && !sameAutomationOriginal(firstPolicy,e.policy_original)) return false; firstPolicy=e.policy_original;
    const c=o.candidate;
    if(!keys(c,"institute_id customer_id policy_original_id rule source due_at valid_until captured_at state external_message_sent delivery_authorized")
      || !keys(c.rule,"trigger enabled offset_us") || !keys(c.source,"institute_id customer_id source_id source_kind occurred_at expires_at remaining")
      || !validEventCandidate(c,institute,customer) || c.state!=="due" || c.rule.trigger!=="rebooking" || c.source.source_kind!=="care_episode"
      || instant(c.captured_at)!==capture || c.policy_original_id!==e.policy_original.id || instant(c.source.occurred_at)!<instant(e.customer.created_at)!) return false;
    const rule=e.policy_original.policy.rules.find(r=>r.trigger==="rebooking"); if(!rule || rule.enabled!==c.rule.enabled || rule.offset_us!==c.rule.offset_us) return false;
    const reason=e.lifecycle_unavailable_reason, life=e.lifecycle_original;
    if(life===null) { if(reason!=="declaration_absent") return false; }
    else {
      if(!lifecycle(life,institute,customer) || ![null,"calendar_absent","future_declaration","future_calendar"].includes(reason as string|null)) return false;
      const future=instant(life.created_at)!>capture;
      if(reason==="future_declaration" ? !future : reason!=="calendar_absent" && future) return false;
    }
  }
  return true;
}
