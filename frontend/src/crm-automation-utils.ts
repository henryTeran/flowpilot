import { certificationInstant as instant } from "./certification-utils";
export const automationTriggers = ["birthday","post_service","rebooking","inactivity","package_expiry","subscription_renewal"] as const;
export type AutomationTrigger = typeof automationTriggers[number];
export type AutomationRule = { trigger: AutomationTrigger; enabled: boolean; offset_us: string };
export type AutomationPolicy = { institute_id: string; rules: AutomationRule[] };
export type AutomationTerms = { policy: AutomationPolicy; previous_policy_id: string | null; reason: string; idempotency_key: string };
export type AutomationOriginal = AutomationTerms & { id: string; institute_id: string; actor_id: string; created_at: string };
const text = (v: unknown,max=80): v is string => typeof v === "string" && !!v && v.trim()===v && v.length<=max;
export function validAutomationPolicy(v: unknown,institute: string): v is AutomationPolicy {
  const p = v as AutomationPolicy;
  if (!p || !text(p.institute_id) || p.institute_id!==institute || !Array.isArray(p.rules) || p.rules.length!==6) return false;
  const seen = new Set<string>();
  for (const r of p.rules) {
    if (!r || !automationTriggers.includes(r.trigger) || typeof r.enabled!=="boolean"
      || typeof r.offset_us!=="string" || r.offset_us.trim()!==r.offset_us || !/^(0|[1-9][0-9]*)$/.test(r.offset_us) || r.offset_us.length>18
      || BigInt(r.offset_us)>253402300799999999n || seen.has(r.trigger)) return false;
    if (r.trigger==="birthday" && r.offset_us!=="0" || ["rebooking","inactivity"].includes(r.trigger) && r.offset_us==="0") return false;
    seen.add(r.trigger);
  }
  return seen.size===6;
}
export function validAutomationTerms(v: unknown,institute: string): v is AutomationTerms {
  const t = v as AutomationTerms;
  return !!t && validAutomationPolicy(t.policy,institute) && (t.previous_policy_id===null || text(t.previous_policy_id))
    && text(t.reason,240) && t.reason.length>=3 && text(t.idempotency_key,120);
}
export function validAutomationOriginal(v: unknown,institute: string): v is AutomationOriginal {
  const r = v as AutomationOriginal;
  return validAutomationTerms(r,institute) && text(r.id) && r.institute_id===institute && r.previous_policy_id!==r.id
    && text(r.actor_id,160) && instant(r.created_at)!==undefined;
}
export function matchesAutomationReceipt(r: AutomationOriginal,t: AutomationTerms,actor: string) {
  return validAutomationOriginal(r,r?.institute_id) && validAutomationTerms(t,r.institute_id)
    && r.actor_id===actor && r.reason===t.reason && r.idempotency_key===t.idempotency_key && r.previous_policy_id===t.previous_policy_id
    && r.policy.rules.every((rule,i) => { const other=t.policy.rules[i];return rule.trigger===other.trigger && rule.enabled===other.enabled && rule.offset_us===other.offset_us; });
}
export function sameAutomationOriginal(a: AutomationOriginal,b: AutomationOriginal) {
  return validAutomationOriginal(a,a?.institute_id) && validAutomationOriginal(b,a.institute_id) && a.id===b.id
    && matchesAutomationReceipt(a,b,b.actor_id) && instant(a.created_at)===instant(b.created_at);
}
