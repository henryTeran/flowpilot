import { certificationInstant as instant } from "./certification-utils";
import { validAutomationPolicy, type AutomationRule, automationTriggers } from "./crm-automation-utils";
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
