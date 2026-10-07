import { certificationInstant as instant } from "./certification-utils";
import { crmUnsigned } from "./crm-billing-utils";

export type SegmentPolicy = { institute_id: string; observation_us: number; new_customer_us: number;
  at_risk_us: number; dormant_us: number; loyal_min_tickets: number; vip_min_tickets: number;
  vip_currency: "CHF" | "EUR"; vip_gross_minor: string };
export type PolicyTerms = { policy: SegmentPolicy; previous_policy_id: string | null; reason: string; idempotency_key: string };
export type PolicyOriginal = PolicyTerms & { id: string; institute_id: string; actor_id: string; created_at: string };
const text = (v: unknown, max = 80): v is string => typeof v === "string" && !!v && v.trim() === v && v.length <= max;
const positive = (v: unknown): v is number => Number.isSafeInteger(v) && (v as number) > 0;
const policyKeys = ["institute_id", "observation_us", "new_customer_us", "at_risk_us", "dormant_us",
  "loyal_min_tickets", "vip_min_tickets", "vip_currency", "vip_gross_minor"] as const;

export function validSegmentPolicy(value: unknown, institute: string): value is SegmentPolicy {
  const p = value as SegmentPolicy;
  return !!p && text(p.institute_id) && p.institute_id === institute
    && positive(p.observation_us) && positive(p.new_customer_us) && positive(p.at_risk_us)
    && positive(p.dormant_us) && positive(p.loyal_min_tickets) && positive(p.vip_min_tickets)
    && p.at_risk_us < p.dormant_us && p.dormant_us < p.observation_us
    && p.new_customer_us <= p.observation_us && p.loyal_min_tickets < p.vip_min_tickets
    && ["CHF", "EUR"].includes(p.vip_currency) && crmUnsigned(p.vip_gross_minor) !== undefined;
}
export function sameSegmentPolicy(a: SegmentPolicy, b: SegmentPolicy): boolean {
  return policyKeys.every(key => a[key] === b[key]);
}
export function validPolicyTerms(value: unknown, institute: string): value is PolicyTerms {
  const r = value as PolicyTerms;
  return !!r && validSegmentPolicy(r.policy, institute) && text(r.reason, 240) && r.reason.length >= 3
    && text(r.idempotency_key, 120) && (r.previous_policy_id === null || text(r.previous_policy_id));
}
export function validPolicyOriginal(value: unknown, institute: string): value is PolicyOriginal {
  const r = value as PolicyOriginal;
  return validPolicyTerms(r, institute) && text(r.id) && r.institute_id === institute && text(r.actor_id, 160)
    && r.previous_policy_id !== r.id && instant(r.created_at) !== undefined;
}
export function matchesPolicyReceipt(r: PolicyOriginal, terms: PolicyTerms, actor: string): boolean {
  return r.actor_id === actor && sameSegmentPolicy(r.policy, terms.policy)
    && r.previous_policy_id === terms.previous_policy_id && r.reason === terms.reason && r.idempotency_key === terms.idempotency_key;
}
export function samePolicyOriginal(a: PolicyOriginal, b: PolicyOriginal): boolean {
  return a.id === b.id && a.institute_id === b.institute_id && matchesPolicyReceipt(a, b, b.actor_id)
    && instant(a.created_at) === instant(b.created_at);
}
