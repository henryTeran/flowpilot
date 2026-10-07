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
