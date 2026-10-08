import { certificationInstant as instant } from "./certification-utils";
import { revenueOriginalFingerprint } from "./revenue-scenario-utils";

export const optimizerFactors = ["revenue_score", "utilization_score", "continuity_score", "client_preference_score",
  "employee_preference_score", "idle_gap_penalty", "overtime_penalty", "resource_conflict_penalty"] as const;
export type OptimizerFactor = typeof optimizerFactors[number];
export const optimizerBases = { revenue_score: "catalog_reference", utilization_score: "proposed_duration_over_free_window",
  continuity_score: "recorded_continuity_indicator", client_preference_score: "declared_client_preference_indicator",
  employee_preference_score: "declared_employee_preference_indicator", idle_gap_penalty: "elapsed_start_delay",
  overtime_penalty: "beyond_declared_working_window", resource_conflict_penalty: "captured_conflict_indicator" } as const;
export type OptimizerRule = { factor: OptimizerFactor; weight: { numerator: string; denominator: string };
  basis: "disabled" | typeof optimizerBases[OptimizerFactor]; ceiling: string | null;
  currency: "CHF" | "EUR" | null; price_mode: "member" | "passage" | null; reason: string };
export type OptimizerTerms = { rules: OptimizerRule[]; normalization: "exact_unit_interval_explicit_ceiling_saturation" };
export type OptimizerPolicyRequest = { terms: OptimizerTerms; reason: string; idempotency_key: string };
export type OptimizerPolicyOriginal = OptimizerPolicyRequest & { id: string; institute_id: string; actor_id: string; created_at: string;
  action: "scoring_assumptions_only_no_booking_or_contact" };
export type OptimizerPolicyEnvelope = { original: OptimizerPolicyOriginal; fingerprint: string };
export type OptimizerPolicyAudit = { institute_id: string; captured_at: string; offset: number; limit: number; total: number;
  originals: OptimizerPolicyEnvelope[]; basis: "verified_retained_scoring_assumptions_not_an_active_default" };
const keys = (v: unknown, names: string): v is Record<string, unknown> => !!v && typeof v === "object" && !Array.isArray(v)
  && Object.keys(v).sort().join(" ") === names.split(" ").sort().join(" ");
const text = (v: unknown, max: number, min = 1): v is string => typeof v === "string" && v === v.trim()
  && Array.from(v).length >= min && Array.from(v).length <= max;
const id = (v: unknown, max = 80): v is string => text(v, max) && !/[\x00-\x1f]/.test(v);
const unsigned = (v: unknown): v is string => typeof v === "string" && /^(0|[1-9][0-9]*)$/.test(v) && v.length <= 40;
const positive = (v: unknown): v is string => unsigned(v) && v !== "0";
const count = (v: unknown): v is number => typeof v === "number" && Number.isSafeInteger(v) && v >= 0;
export function validOptimizerRule(v: unknown): v is OptimizerRule {
  if (!keys(v, "factor weight basis ceiling currency price_mode reason") || !optimizerFactors.includes(v.factor as OptimizerFactor)
    || !keys(v.weight, "numerator denominator") || !unsigned(v.weight.numerator) || !positive(v.weight.denominator)
    || !text(v.reason, 240, 3)) return false;
  if (v.weight.numerator === "0") return v.basis === "disabled" && v.ceiling === null && v.currency === null && v.price_mode === null;
  if (v.basis !== optimizerBases[v.factor as OptimizerFactor]) return false;
  if (v.basis === "catalog_reference") return positive(v.ceiling) && ["CHF", "EUR"].includes(String(v.currency)) && ["member", "passage"].includes(String(v.price_mode));
  return v.currency === null && v.price_mode === null && (["elapsed_start_delay", "beyond_declared_working_window"].includes(String(v.basis))
    ? positive(v.ceiling) : v.ceiling === null);
}
export function validOptimizerTerms(v: unknown): v is OptimizerTerms {
  return keys(v, "rules normalization") && v.normalization === "exact_unit_interval_explicit_ceiling_saturation"
    && Array.isArray(v.rules) && v.rules.length === 8 && v.rules.every(validOptimizerRule)
    && new Set(v.rules.map(r => r.factor)).size === 8 && v.rules.some(r => r.weight.numerator !== "0");
}
export function validOptimizerPolicyRequest(v: unknown): v is OptimizerPolicyRequest {
  return keys(v, "terms reason idempotency_key") && validOptimizerTerms(v.terms) && text(v.reason, 240, 3) && id(v.idempotency_key, 120);
}
export function matchesOptimizerPolicyReceipt(e: OptimizerPolicyEnvelope, request: OptimizerPolicyRequest, actor: string) {
  const o = e.original;
  return o.actor_id === actor && o.reason === request.reason && o.idempotency_key === request.idempotency_key
    && o.terms.normalization === request.terms.normalization && o.terms.rules.length === request.terms.rules.length
    && o.terms.rules.every((r, i) => { const s = request.terms.rules[i];
      return r.factor === s.factor && r.basis === s.basis && r.ceiling === s.ceiling && r.currency === s.currency
        && r.price_mode === s.price_mode && r.reason === s.reason && r.weight.numerator === s.weight.numerator && r.weight.denominator === s.weight.denominator;
    });
}
export async function validOptimizerPolicyEnvelope(v: unknown, institute: string): Promise<boolean> {
  try {
    if (!keys(v, "original fingerprint") || typeof v.fingerprint !== "string" || !/^[0-9a-f]{64}$/.test(v.fingerprint)
      || !keys(v.original, "terms reason idempotency_key id institute_id actor_id created_at action")) return false;
    const o = v.original;
    return id(o.id) && o.institute_id === institute && id(o.institute_id) && id(o.actor_id, 160)
      && o.action === "scoring_assumptions_only_no_booking_or_contact"
      && typeof o.created_at === "string" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.(?!000000)\d{6})?Z$/.test(o.created_at)
      && instant(o.created_at) !== undefined
      && validOptimizerPolicyRequest({ terms: o.terms, reason: o.reason, idempotency_key: o.idempotency_key })
      && await revenueOriginalFingerprint(o) === v.fingerprint;
  } catch { return false; }
}
export async function validOptimizerPolicyAudit(v: unknown, institute: string, offset: number): Promise<boolean> {
  if (!count(offset) || !keys(v, "institute_id captured_at offset limit total originals basis") || v.institute_id !== institute
    || v.offset !== offset || v.limit !== 20 || !count(v.total) || v.basis !== "verified_retained_scoring_assumptions_not_an_active_default"
    || !Array.isArray(v.originals) || v.originals.length !== Math.min(20, Math.max(0, v.total-offset))) return false;
  const capture = instant(v.captured_at); if (capture === undefined) return false;
  const seen = new Set<string>(), seenKeys = new Set<string>(); let previous: OptimizerPolicyOriginal | undefined;
  for (const value of v.originals) {
    if (!await validOptimizerPolicyEnvelope(value, institute)) return false;
    const o = (value as OptimizerPolicyEnvelope).original, at = instant(o.created_at)!;
    if (at > capture || seen.has(o.id) || seenKeys.has(o.idempotency_key) || previous && (at < instant(previous.created_at)!
      || at === instant(previous.created_at)! && o.id <= previous.id)) return false;
    seen.add(o.id); seenKeys.add(o.idempotency_key); previous = o;
  }
  return true;
}
