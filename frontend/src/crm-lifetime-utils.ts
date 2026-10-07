import { certificationInstant as instant } from "./certification-utils";
import { crmUnsigned, validRecordedBilling, type BillingRatio, type BillingWindow, type RecordedBilling } from "./crm-billing-utils";
export type LifetimeAssumptions = { institute_id: string; customer_id: string;
  model: "constant_observed_rate_finite_remaining_lifetime_undiscounted_v1"; currency: "CHF" | "EUR";
  expected_active_us: string; activity_fraction: BillingRatio; gross_contribution_margin: BillingRatio; future_relationship_cost_minor: string };
export type LifetimeTerms = { assumptions: LifetimeAssumptions; previous_id: string | null; reason: string; idempotency_key: string };
export type LifetimeOriginal = LifetimeTerms & { id: string; institute_id: string; customer_id: string; actor_id: string; created_at: string };
export type LifetimeScenario = { basis: "declared_remaining_lifetime_scenario"; assumptions: LifetimeAssumptions; billing: RecordedBilling;
  undated_paid_tickets: number; future_paid_tickets: number; assumed_active_until: string | null;
  projected_gross_minor: BillingRatio | null; projected_contribution_minor: BillingRatio | null; remaining_clv_minor: BillingRatio | null;
  unavailable_reason: "stale_window" | "undated_closings" | "future_closings" | "unrepresentable_lifetime" | "unknown_currency" | "no_observed_currency" | "uncertain_amounts" | null;
  complete_customer_history: false; validated_prediction: false; discounted: false };
export type LifetimeRead = { window: BillingWindow; customer: { institute_id: string; customer_id: string; created_at: string };
  original: LifetimeOriginal | null; scenario: LifetimeScenario | null;
  unavailable_reason: "assumptions_absent" | "future_assumptions" | "future_registration" | null };
const text = (v: unknown, max=80): v is string => typeof v === "string" && !!v && v.trim() === v && v.length <= max;
const count = (v: unknown): v is number => Number.isSafeInteger(v) && (v as number) >= 0;
const model = "constant_observed_rate_finite_remaining_lifetime_undiscounted_v1";
const maxInstant = 253402300799999999n;
function fraction(v: unknown): v is BillingRatio {
  const r = v as BillingRatio, n = crmUnsigned(r?.numerator), d = crmUnsigned(r?.denominator);
  return n !== undefined && d !== undefined && d > 0n && n <= d;
}
export function validLifetimeAssumptions(v: unknown, institute: string, customer: string): v is LifetimeAssumptions {
  const a = v as LifetimeAssumptions, duration = crmUnsigned(a?.expected_active_us);
  return !!a && text(a.institute_id) && text(a.customer_id) && a.institute_id === institute && a.customer_id === customer
    && a.model === model && ["CHF","EUR"].includes(a.currency) && duration !== undefined && duration > 0n
    && fraction(a.activity_fraction) && fraction(a.gross_contribution_margin) && crmUnsigned(a.future_relationship_cost_minor) !== undefined;
}
export function validLifetimeTerms(v: unknown, institute: string, customer: string): v is LifetimeTerms {
  const t = v as LifetimeTerms;
  return !!t && validLifetimeAssumptions(t.assumptions,institute,customer) && (t.previous_id === null || text(t.previous_id))
    && text(t.reason,240) && t.reason.length >= 3 && text(t.idempotency_key,120);
}
export function validLifetimeOriginal(v: unknown, institute: string, customer: string): v is LifetimeOriginal {
  const r = v as LifetimeOriginal;
  return validLifetimeTerms(r,institute,customer) && text(r.id) && r.institute_id === institute && r.customer_id === customer
    && r.previous_id !== r.id && text(r.actor_id,160) && instant(r.created_at) !== undefined;
}
export function sameLifetimeAssumptions(a: LifetimeAssumptions,b: LifetimeAssumptions): boolean {
  return validLifetimeAssumptions(a,a?.institute_id,a?.customer_id) && validLifetimeAssumptions(b,a.institute_id,a.customer_id)
    && a.model === b.model && a.currency === b.currency && a.expected_active_us === b.expected_active_us
    && a.future_relationship_cost_minor === b.future_relationship_cost_minor
    && a.activity_fraction.numerator === b.activity_fraction.numerator && a.activity_fraction.denominator === b.activity_fraction.denominator
    && a.gross_contribution_margin.numerator === b.gross_contribution_margin.numerator && a.gross_contribution_margin.denominator === b.gross_contribution_margin.denominator;
}
export function matchesLifetimeReceipt(r: LifetimeOriginal,t: LifetimeTerms,actor: string): boolean {
  return validLifetimeOriginal(r,r?.institute_id,r?.customer_id) && validLifetimeTerms(t,r.institute_id,r.customer_id)
    && r.actor_id === actor && sameLifetimeAssumptions(r.assumptions,t.assumptions)
    && r.previous_id === t.previous_id && r.reason === t.reason && r.idempotency_key === t.idempotency_key;
}
export function sameLifetimeOriginal(a: LifetimeOriginal,b: LifetimeOriginal): boolean {
  return validLifetimeOriginal(a,a?.institute_id,a?.customer_id) && validLifetimeOriginal(b,a.institute_id,a.customer_id)
    && a.id === b.id && matchesLifetimeReceipt(a,b,b.actor_id) && instant(a.created_at) === instant(b.created_at);
}
function exact(v: unknown,n: bigint,d: bigint): boolean {
  let a = n < 0n ? -n : n, b = d;
  while (b) { const t = a%b; a = b; b = t; }
  const r = v as BillingRatio;
  return !!r && typeof r.numerator === "string" && r.numerator.length <= 150 && /^(0|-?[1-9]\d*)$/.test(r.numerator)
    && typeof r.denominator === "string" && r.denominator.length <= 150 && /^[1-9]\d*$/.test(r.denominator)
    && BigInt(r.numerator) === n/a && BigInt(r.denominator) === d/a;
}
export function validLifetimeRead(v: unknown,institute: string,customer: string,startText: string): v is LifetimeRead {
  const r = v as LifetimeRead, w = r?.window, start = instant(w?.start), end = instant(w?.end), captured = instant(w?.captured_at);
  const registered = instant(r?.customer?.created_at);
  if (!r || !w || w.institute_id !== institute || w.customer_id !== customer || start === undefined || start !== instant(startText)
    || end === undefined || captured !== end || start >= end || registered === undefined || r.customer.institute_id !== institute || r.customer.customer_id !== customer
    || r.original !== null && !validLifetimeOriginal(r.original,institute,customer)) return false;
  const original = r.original;
  const unavailable = original === null ? "assumptions_absent" : instant(original.created_at)! > end ? "future_assumptions" : registered > end ? "future_registration" : null;
  if (r.unavailable_reason !== unavailable) return false;
  if (unavailable) return r.scenario === null;
  const s = r.scenario;
  if (!s || !original || s.basis !== "declared_remaining_lifetime_scenario" || !sameLifetimeAssumptions(s.assumptions,original.assumptions)
    || s.complete_customer_history !== false || s.validated_prediction !== false || s.discounted !== false
    || !count(s.undated_paid_tickets) || !count(s.future_paid_tickets)
    || !validRecordedBilling(s.billing,institute,customer,{ start: w.start,end: w.end,captured_at: w.captured_at })) return false;
  const terms = original.assumptions, until = end+BigInt(terms.expected_active_us), selected = s.billing.currencies.find(g => g.currency === terms.currency);
  const reason = s.undated_paid_tickets ? "undated_closings" : s.future_paid_tickets ? "future_closings"
    : until > maxInstant ? "unrepresentable_lifetime" : s.billing.unknown_currency_tickets ? "unknown_currency"
    : !selected ? "no_observed_currency" : selected.missing_amount_tickets+selected.invalid_amount_tickets ? "uncertain_amounts" : null;
  const hasUntil = !s.undated_paid_tickets && !s.future_paid_tickets && until <= maxInstant;
  if (s.unavailable_reason !== reason || (hasUntil ? instant(s.assumed_active_until) !== until : s.assumed_active_until !== null)) return false;
  if (reason) return s.projected_gross_minor === null && s.projected_contribution_minor === null && s.remaining_clv_minor === null;
  const activity = terms.activity_fraction, margin = terms.gross_contribution_margin;
  const gn = BigInt(selected!.known_gross_minor)*BigInt(terms.expected_active_us)*BigInt(activity.numerator);
  const gd = (end-start)*BigInt(activity.denominator), cn = gn*BigInt(margin.numerator), cd = gd*BigInt(margin.denominator);
  return exact(s.projected_gross_minor,gn,gd) && exact(s.projected_contribution_minor,cn,cd)
    && exact(s.remaining_clv_minor,cn-BigInt(terms.future_relationship_cost_minor)*cd,cd);
}
