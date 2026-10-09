import {certificationInstant as instant} from "./certification-utils";
import {validEventCandidate,type EventCandidate} from "./crm-event-utils";
export type ReturnOpportunities={institute_id:string;captured_at:string;source_digest:string;source:"observed_care_declared_rebooking_rule";total_candidates:number;examined_customers:number;already_booked_customers:number;scheduled_customers:number;disabled_customers:number;no_candidate_customers:number;diagnostics:Record<string,number>;candidates:EventCandidate[];page_limit:20;estimated_value:null;delivery_authorized:false;action_executed:false;complete_customer_history:false};
const keys=(v:unknown,names:string):v is Record<string,unknown>=>!!v && typeof v==="object" && !Array.isArray(v) && Object.keys(v).sort().join(" ")===names.split(" ").sort().join(" ");
const count=(v:unknown):v is number=>Number.isSafeInteger(v) && (v as number)>=0;
const id=(v:unknown):v is string=>typeof v==="string" && !!v && v.trim()===v && Array.from(v).length<=80 && !/[\x00-\x1f]/.test(v);
export function validReturnOpportunities(v:unknown,institute:string,capture:string):v is ReturnOpportunities{
  if(!keys(v,"institute_id captured_at source_digest source total_candidates examined_customers already_booked_customers scheduled_customers disabled_customers no_candidate_customers diagnostics candidates page_limit estimated_value delivery_authorized action_executed complete_customer_history")
    || v.institute_id!==institute || instant(capture)===undefined || instant(v.captured_at)!==instant(capture) || typeof v.source_digest!=="string" || !/^[0-9a-f]{64}$/.test(v.source_digest)
    || v.source!=="observed_care_declared_rebooking_rule" || v.page_limit!==20 || v.estimated_value!==null || v.delivery_authorized!==false || v.action_executed!==false || v.complete_customer_history!==false)return false;
  const counts=[v.total_candidates,v.examined_customers,v.already_booked_customers,v.scheduled_customers,v.disabled_customers,v.no_candidate_customers];
  if(!counts.every(count) || counts.filter((_,index)=>index!==1).reduce((n,c)=>n+BigInt(c as number),0n)!==BigInt(v.examined_customers as number)
    || !Array.isArray(v.candidates) || v.candidates.length!==Math.min(20,v.total_candidates as number) || new Set(v.candidates.map(c=>c?.customer_id)).size!==v.candidates.length)return false;
  const diagnostics=["policy_absent","future_policy","future_registration","care_unavailable","care_unlinked_ticket","care_invalid_owner_or_service","care_invalid_actual_times","invalid_event_timing"];
  if(!v.diagnostics || typeof v.diagnostics!=="object" || Array.isArray(v.diagnostics) || Object.entries(v.diagnostics).some(([key,n])=>!diagnostics.includes(key) || !count(n)))return false;
  return v.candidates.every(c=>keys(c,"institute_id customer_id policy_original_id rule source due_at valid_until captured_at state external_message_sent delivery_authorized")
    && id(c.customer_id) && keys(c.rule,"trigger enabled offset_us") && keys(c.source,"institute_id customer_id source_id source_kind occurred_at expires_at remaining")
    && validEventCandidate(c,institute,c.customer_id) && c.rule.trigger==="rebooking" && c.source.source_kind==="care_episode" && c.state==="due" && instant(c.captured_at)===instant(capture));
}
