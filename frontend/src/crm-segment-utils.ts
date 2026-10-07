import { certificationInstant as instant } from "./certification-utils";
import { validRecordedBilling, type RecordedBilling } from "./crm-billing-utils";
import { validPolicyOriginal, sameSegmentPolicy, type SegmentPolicy, type PolicyOriginal } from "./crm-policy-utils";

type Registration = { institute_id: string; customer_id: string; created_at: string };
type State = "NEW" | "ACTIVE" | "LOYAL" | "VIP" | "AT_RISK" | "DORMANT" | null;
type ObservedSegment = { basis: "declared_policy_observed_billing"; policy: SegmentPolicy; customer: Registration;
  billing: RecordedBilling; undated_paid_tickets: number; state: State; reason: string; complete_customer_history: false };
export type SegmentProfile = { institute_id: string; customer_id: string; captured_at: string; customer: Registration;
  policy_original: PolicyOriginal | null; undated_paid_tickets: number; future_paid_tickets: number;
  segment: ObservedSegment | null; unavailable_reason: string | null; complete_customer_history: false };
const count = (v: unknown): v is number => Number.isSafeInteger(v) && (v as number) >= 0;
const earliest = -62135596800000000n;

function classification(p: SegmentPolicy, age: bigint, b: RecordedBilling, undated: number): [State, string] {
  if (undated) return [null, "undated_closings"];
  if (b.closed_tickets === 0) return age <= BigInt(p.new_customer_us) ? ["NEW", "recent_registration"] : [null, "no_observed_closing"];
  const recency = BigInt(b.recorded_recency_us!);
  if (recency >= BigInt(p.dormant_us)) return ["DORMANT", "dormant_recency"];
  if (recency >= BigInt(p.at_risk_us)) return ["AT_RISK", "risk_recency"];
  if (b.closed_tickets >= p.vip_min_tickets) {
    const g = b.currencies.find(row => row.currency === p.vip_currency);
    if (BigInt(g?.known_gross_minor || "0") >= BigInt(p.vip_gross_minor)) return ["VIP", "vip_count_and_gross"];
    if (b.unknown_currency_tickets || g && (g.missing_amount_tickets || g.invalid_amount_tickets)) return [null, "uncertain_vip_gross"];
    return ["LOYAL", "loyal_count"];
  }
  return b.closed_tickets >= p.loyal_min_tickets ? ["LOYAL", "loyal_count"] : ["ACTIVE", "recent_activity"];
}
export function validSegmentProfile(value: unknown, institute: string, customer: string): value is SegmentProfile {
  const r = value as SegmentProfile;
  if (!r || r.institute_id !== institute || r.customer_id !== customer || !r.customer
    || r.customer.institute_id !== institute || r.customer.customer_id !== customer || r.complete_customer_history !== false
    || !count(r.undated_paid_tickets) || !count(r.future_paid_tickets)) return false;
  const captured = instant(r.captured_at), registered = instant(r.customer.created_at);
  if (captured === undefined || registered === undefined) return false;
  const original = r.policy_original;
  if (original !== null && !validPolicyOriginal(original, institute)) return false;
  const unavailable = original === null ? "policy_absent" : instant(original.created_at)! > captured ? "future_policy"
    : registered > captured ? "future_registration" : r.future_paid_tickets ? "future_closings"
    : captured-BigInt(original.policy.observation_us) < earliest ? "unrepresentable_horizon" : null;
  if (r.unavailable_reason !== unavailable) return false;
  if (unavailable !== null) return r.segment === null;
  if (!original) return false;
  const s = r.segment, p = original.policy;
  if (!s || s.basis !== "declared_policy_observed_billing" || !s.policy || !sameSegmentPolicy(s.policy, p)
    || !s.customer || s.customer.institute_id !== institute || s.customer.customer_id !== customer
    || instant(s.customer.created_at) !== registered || s.undated_paid_tickets !== r.undated_paid_tickets
    || s.complete_customer_history !== false || !validRecordedBilling(s.billing, institute, customer)) return false;
  const w = s.billing.window;
  if (instant(w.end) !== captured || instant(w.captured_at) !== captured
    || instant(w.start) !== captured-BigInt(p.observation_us)) return false;
  const [state, reason] = classification(p, captured-registered, s.billing, r.undated_paid_tickets);
  return s.state === state && s.reason === reason;
}
