import { validLifecycleRead, type LifecycleRead } from "./crm-lifecycle-utils";
import { certificationInstant as instant } from "./certification-utils";
import { validAutomationOriginal, validAutomationPolicy, type AutomationOriginal, type AutomationRule, automationTriggers } from "./crm-automation-utils";
export type EventAnchor = { institute_id:string; customer_id:string; source_id:string; source_kind:"care_episode"|"package"|"membership"|"birthday"; occurred_at:string; expires_at:string|null; remaining:number|null };
export type EventCandidate = { institute_id:string; customer_id:string; policy_original_id:string; rule:AutomationRule; source:EventAnchor; due_at:string; valid_until:string|null; captured_at:string; state:"scheduled"|"due"|"expired"|"exhausted"|"disabled"; external_message_sent:false; delivery_authorized:false };
const text=(v:unknown):v is string=>typeof v==="string" && v.length>0 && v.length<=80 && v.trim()===v;
export function validEventAnchor(v:unknown,institute:string,customer:string):v is EventAnchor {
  const a=v as EventAnchor;if(!a || !text(institute) || !text(customer) || a.institute_id!==institute || a.customer_id!==customer || !text(a.source_id))return false;
  const start=instant(a.occurred_at);if(start===undefined)return false;
  if(a.source_kind==="care_episode")return a.expires_at===null && a.remaining===null;
  if(!["birthday","package","membership"].includes(a.source_kind))return false;
  const end=instant(a.expires_at);return end!==undefined && end>start && (a.source_kind==="package" ? Number.isSafeInteger(a.remaining) && a.remaining!==null && a.remaining>=0 : a.remaining===null);
}
export function validEventCandidate(v:unknown,institute:string,customer:string):v is EventCandidate {
  const c=v as EventCandidate;if(!c || c.institute_id!==institute || c.customer_id!==customer || !text(c.policy_original_id)
    || c.external_message_sent!==false || c.delivery_authorized!==false || !validEventAnchor(c.source,institute,customer) || !c.rule)return false;
  // Reuse the canonical six-rule validator to validate this rule without numeric coercion.
  const rules=automationTriggers.map(trigger=>trigger===c.rule.trigger ? c.rule : {trigger,enabled:false,offset_us:["rebooking","inactivity"].includes(trigger)?"1":"0"});
  if(!automationTriggers.includes(c.rule.trigger) || !validAutomationPolicy({institute_id:institute,rules},institute))return false;
  const kind={birthday:"birthday",post_service:"care_episode",rebooking:"care_episode",inactivity:"care_episode",package_expiry:"package",subscription_renewal:"membership"}[c.rule.trigger];
  if(c.source.source_kind!==kind)return false;
  const start=instant(c.source.occurred_at)!,end=c.source.expires_at===null ? null : instant(c.source.expires_at)!,captured=instant(c.captured_at),due=instant(c.due_at);
  if(captured===undefined || due===undefined || (kind!=="birthday" && start>captured) || (c.valid_until===null ? end!==null : instant(c.valid_until)!==end))return false;
  const offset=BigInt(c.rule.offset_us), raw=["package_expiry","subscription_renewal"].includes(c.rule.trigger) ? end!-offset : start+offset;
  const expected=raw<start ? start : raw;if(due!==expected)return false;
  let state:EventCandidate["state"]=captured<due ? "scheduled" : "due";
  if(end!==null && captured>=end)state="expired";
  if(kind==="package" && c.source.remaining===0)state="exhausted";
  if(!c.rule.enabled)state="disabled";
  return c.state===state;
}

export type EventDecision={event_key:string;candidate:EventCandidate;state:"scheduled"|"due"|"blocked"|"cancelled"|"expired"|"processed";reason:"candidate"|"source_uncertain"|"rule_disabled"|"package_exhausted"|"occurrence_expired"|"superseded"|"birthday_declared_unknown"|"explicit_cancellation"|"already_processed";evaluated_at:string};
export type EventRevision={id:string;institute_id:string;customer_id:string;event_key:string;capture_id:string;previous_id:string|null;decision:EventDecision};
export type EventPage={institute_id:string;customer_id:string;total:number;offset:number;limit:number;revisions:EventRevision[]};
function pythonUtc(value:string){
 const us=instant(value)!;const seconds=us>=0n ? us/1000000n : (us-999999n)/1000000n;
 const fraction=us-seconds*1000000n,base=new Date(Number(seconds*1000n)).toISOString().slice(0,19);
 return base+(fraction ? "."+String(fraction).padStart(6,"0") : "")+"+00:00";
}
export async function eventIdentity(c:EventCandidate):Promise<string>{
 const term=["package","membership"].includes(c.source.source_kind) ? pythonUtc(c.source.expires_at!) : null;
 const parts=[c.institute_id,c.customer_id,c.rule.trigger,c.source.source_kind,c.source.source_id,term];
 const canonical=JSON.stringify(parts).replace(/[\u007f-\uffff]/g,char=>"\\u"+char.charCodeAt(0).toString(16).padStart(4,"0"));
 return Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256",new TextEncoder().encode(canonical))),b=>b.toString(16).padStart(2,"0")).join("");
}
export async function validEventDecision(v:unknown,institute:string,customer:string):Promise<boolean>{
 const d=v as EventDecision;if(!d || !validEventCandidate(d.candidate,institute,customer))return false;
 const evaluated=instant(d.evaluated_at);if(evaluated===undefined || evaluated<instant(d.candidate.captured_at)!)return false;
 const allowed:Record<EventDecision["state"],string[]>={scheduled:["candidate"],due:["candidate"],blocked:["source_uncertain"],cancelled:["rule_disabled","package_exhausted","superseded","birthday_declared_unknown","explicit_cancellation"],expired:["occurrence_expired"],processed:["already_processed"]};
 if(d.reason==="candidate" && d.state!==d.candidate.state || d.reason==="occurrence_expired" && d.candidate.state!=="expired"
  || d.reason==="rule_disabled" && d.candidate.state!=="disabled" || d.reason==="package_exhausted" && d.candidate.state!=="exhausted")return false;
 return Object.prototype.hasOwnProperty.call(allowed,d.state) && allowed[d.state].includes(d.reason) && d.event_key===await eventIdentity(d.candidate);
}
export async function validEventRevision(v:unknown,institute:string,customer:string):Promise<boolean>{
 const r=v as EventRevision;return !!r && r.institute_id===institute && r.customer_id===customer && text(r.id) && text(r.capture_id)
  && (r.previous_id===null || text(r.previous_id) && r.previous_id!==r.id) && r.event_key===r.decision?.event_key && await validEventDecision(r.decision,institute,customer);
}
export async function validEventPage(v:unknown,institute:string,customer:string,offset:number,limit:number):Promise<boolean>{
 const p=v as EventPage;if(!p || p.institute_id!==institute || p.customer_id!==customer || p.offset!==offset || p.limit!==limit
  || !Number.isSafeInteger(p.total) || p.total<0 || !Number.isSafeInteger(offset) || offset<0 || !Number.isInteger(limit) || limit<1 || limit>50 || !Array.isArray(p.revisions)
  || p.revisions.length!==Math.min(limit,Math.max(0,p.total-offset)))return false;
 let previous="";const ids=new Set<string>();
 for(const r of p.revisions){if(!await validEventRevision(r,institute,customer) || r.event_key<=previous || ids.has(r.id))return false;previous=r.event_key;ids.add(r.id);}
 return true;
}

export type EventRequest={action:"reconcile"|"cancel"|"process"|"process_due";event_key:string|null;expected_revision_id:string|null;reason:string;idempotency_key:string};
export type EventSource={institute_id:string;customer_id:string;captured_at:string;customer:{institute_id:string;customer_id:string;created_at:string};policy_original:AutomationOriginal|null;lifecycle:LifecycleRead;anchors:EventAnchor[];candidates:EventCandidate[];diagnostics:Record<string,number>;complete_customer_history:false;external_message_sent:false;delivery_authorized:false};
export type EventCapture={id:string;institute_id:string;customer_id:string;actor_id:string;request:EventRequest;captured_at:string;source:EventSource;revisions:EventRevision[]};
export function validEventRequest(v:unknown):v is EventRequest{
 const r=v as EventRequest;if(!r || !["reconcile","cancel","process","process_due"].includes(r.action) || typeof r.reason!=="string" || r.reason.trim()!==r.reason || r.reason.length<3 || r.reason.length>240 || typeof r.idempotency_key!=="string" || !r.idempotency_key || r.idempotency_key.trim()!==r.idempotency_key || r.idempotency_key.length>120)return false;
 return ["reconcile","process_due"].includes(r.action) ? r.event_key===null && r.expected_revision_id===null : text(r.event_key) && text(r.expected_revision_id);
}
const diagnosticKeys=["policy_absent","future_policy","future_registration","birthday_unavailable","care_unavailable","care_unlinked_ticket","care_invalid_owner_or_service","care_invalid_actual_times","invalid_event_timing","package_absent","membership_absent","invalid_package","invalid_membership"];
export function validEventSource(v:unknown,institute:string,customer:string):v is EventSource{
 const s=v as EventSource,clock=instant(s?.captured_at),registered=instant(s?.customer?.created_at);
 if(!s || !text(institute) || !text(customer) || s.institute_id!==institute || s.customer_id!==customer || clock===undefined || registered===undefined || s.customer.institute_id!==institute || s.customer.customer_id!==customer || s.complete_customer_history!==false || s.external_message_sent!==false || s.delivery_authorized!==false || !validLifecycleRead(s.lifecycle,institute,customer) || instant(s.lifecycle.captured_at)!==clock || instant(s.lifecycle.customer.created_at)!==registered || s.policy_original!==null && !validAutomationOriginal(s.policy_original,institute) || !Array.isArray(s.anchors) || !Array.isArray(s.candidates) || !s.diagnostics || Object.keys(s.diagnostics).length!==diagnosticKeys.length || diagnosticKeys.some(k=>!Number.isSafeInteger(s.diagnostics[k]) || s.diagnostics[k]<0))return false;
 const d=s.diagnostics,p=s.policy_original;
 if(d.policy_absent!==Number(p===null) || d.future_policy!==Number(p!==null && instant(p.created_at)!>clock) || d.future_registration!==Number(registered>clock) || d.birthday_unavailable!==Number(!s.lifecycle.birthday?.occurrence_start) || ["policy_absent","future_policy","future_registration","birthday_unavailable","care_unavailable","invalid_event_timing","package_absent","membership_absent"].some(k=>d[k]>1))return false;
 const identities=new Set<string>();let latest:EventAnchor|undefined;
 for(const a of s.anchors){
  if(!validEventAnchor(a,institute,customer))return false;
  const key=JSON.stringify([a.source_kind,a.source_id]);if(identities.has(key))return false;identities.add(key);
  if(a.source_kind==="birthday"){
   const b=s.lifecycle.birthday;if(!b || a.source_id!==b.anniversary_on || instant(a.occurred_at)!==instant(b.occurrence_start) || instant(a.expires_at)!==instant(b.occurrence_end))return false;
  }else if(instant(a.occurred_at)!<registered || instant(a.occurred_at)!>clock)return false;
  if(a.source_kind==="care_episode" && (!latest || instant(a.occurred_at)!>instant(latest.occurred_at)! || instant(a.occurred_at)===instant(latest.occurred_at) && a.source_id>latest.source_id))latest=a;
 }
 if(s.anchors.filter(a=>a.source_kind==="birthday").length!==Number(!d.birthday_unavailable) || (d.care_unlinked_ticket || d.care_invalid_owner_or_service || d.care_invalid_actual_times || d.care_unavailable) && latest)return false;
 if(!p || d.future_policy || d.future_registration || d.invalid_event_timing)return s.candidates.length===0;
 const expected=new Map<string,AutomationRule>();
 for(const rule of p.policy.rules){const kind={birthday:"birthday",post_service:"care_episode",rebooking:"care_episode",inactivity:"care_episode",package_expiry:"package",subscription_renewal:"membership"}[rule.trigger];
  for(const a of s.anchors.filter(a=>a.source_kind===kind && (!["rebooking","inactivity"].includes(rule.trigger) || a===latest)))expected.set(JSON.stringify([rule.trigger,a.source_kind,a.source_id]),rule);
 }
 if(s.candidates.length!==expected.size)return false;
 for(const c of s.candidates){
  if(!validEventCandidate(c,institute,customer) || c.policy_original_id!==p.id || instant(c.captured_at)!==clock)return false;
  const key=JSON.stringify([c.rule.trigger,c.source.source_kind,c.source.source_id]),rule=expected.get(key),anchor=s.anchors.find(a=>a.source_kind===c.source.source_kind && a.source_id===c.source.source_id);
  if(!rule || !anchor || rule.enabled!==c.rule.enabled || rule.offset_us!==c.rule.offset_us || instant(anchor.occurred_at)!==instant(c.source.occurred_at) || (anchor.expires_at===null ? c.source.expires_at!==null : instant(anchor.expires_at)!==instant(c.source.expires_at)) || anchor.remaining!==c.source.remaining)return false;expected.delete(key);
 }
 return expected.size===0;
}
export async function validEventCapture(v:unknown,institute:string,customer:string):Promise<boolean>{
 const c=v as EventCapture,clock=instant(c?.captured_at);if(!c || !text(c.id) || c.institute_id!==institute || c.customer_id!==customer || typeof c.actor_id!=="string" || !c.actor_id || c.actor_id.trim()!==c.actor_id || c.actor_id.length>160 || !validEventRequest(c.request) || clock===undefined || !validEventSource(c.source,institute,customer) || instant(c.source.captured_at)!==clock || !Array.isArray(c.revisions))return false;
 const keys=new Set<string>(),ids=new Set<string>();
 for(const r of c.revisions){if(!await validEventRevision(r,institute,customer) || instant(r.decision.evaluated_at)!>clock || keys.has(r.event_key) || ids.has(r.id))return false;keys.add(r.event_key);ids.add(r.id);}
 for(const candidate of c.source.candidates)if(!keys.has(await eventIdentity(candidate)))return false;
 if(["cancel","process"].includes(c.request.action)){
  const target=c.revisions.find(r=>r.event_key===c.request.event_key);
  if(!target || (c.request.action==="cancel" ? target.decision.state!=="cancelled" || target.decision.reason!=="explicit_cancellation" : target.decision.state!=="processed" || target.decision.reason!=="already_processed"))return false;
 }
 return true;
}
export function sameEventRequest(a:EventRequest,b:EventRequest){return validEventRequest(a) && validEventRequest(b) && a.action===b.action && a.event_key===b.event_key && a.expected_revision_id===b.expected_revision_id && a.reason===b.reason && a.idempotency_key===b.idempotency_key;}
export async function matchesEventCapture(v:unknown,institute:string,customer:string,terms:EventRequest,actor:string){const c=v as EventCapture;return await validEventCapture(c,institute,customer) && c.actor_id===actor && sameEventRequest(c.request,terms);}

function canonicalReceipt(v:unknown,key=""):string{
 if(typeof v==="string" && ["created_at","captured_at","occurred_at","expires_at","due_at","valid_until","evaluated_at","occurrence_start","occurrence_end"].includes(key))return instant(v)?.toString() || JSON.stringify(v);
 if(Array.isArray(v))return "["+v.map(x=>canonicalReceipt(x)).join(",")+"]";
 if(v && typeof v==="object")return "{"+Object.entries(v).sort(([a],[b])=>a<b?-1:a>b?1:0).map(([k,x])=>JSON.stringify(k)+":"+canonicalReceipt(x,k)).join(",")+"}";
 return JSON.stringify(v);
}
export async function sameEventCapture(a:unknown,b:unknown,institute:string,customer:string){return await validEventCapture(a,institute,customer) && await validEventCapture(b,institute,customer) && canonicalReceipt(a)===canonicalReceipt(b);}
