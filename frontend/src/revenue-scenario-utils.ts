import { certificationInstant as instant } from "./certification-utils";
import { validRevenueBilling, type RevenueBilling } from "./revenue-utils";
export type RevenueAssumptions = { model: "constant_recorded_gross_rate_v1"; observed_start: string; observed_end: string; projected_start: string; projected_end: string; currency: "CHF" | "EUR"; activity_fraction: { numerator: string; denominator: string } };
export type RevenueScenarioOriginal = { institute_id: string; actor_id: string; assumptions: RevenueAssumptions; evidence: RevenueBilling;
  basis: "explicit_constant_historical_rate_scenario"; projected_gross_minor: { numerator: string; denominator: string } | null;
  confidence: "conditional_unvalidated_scenario"; unavailable_reason: "unknown_currency" | "undated_paid_tickets" | "no_selected_currency" | "uncertain_amounts" | null;
  validated_prediction: false; action_executed: false; id: string; reason: string; idempotency_key: string; created_at: string; retained: true };
export type RevenueScenarioEnvelope = { original: RevenueScenarioOriginal; fingerprint: string };
export type RevenueScenarioReference = { original_id: string; fingerprint: string };
export type RevenueScenarioSelection = { baseline: RevenueScenarioReference; alternatives: RevenueScenarioReference[] };
export type RevenueScenarioComparison = {
  institute_id: string; captured_at: string; baseline_original_id: string; selected_count: number;
  variants: { original: RevenueScenarioEnvelope; is_baseline: boolean; same_source_capture: boolean; same_recorded_billing_aggregates: boolean;
    difference_from_baseline_minor: { numerator: string; denominator: string } | null;
    difference_unavailable_reason: "currency_difference" | "model_difference" | "observed_period_difference" | "projected_period_difference" | "unavailable_projection" | null;
    difference_basis: "comparison_only_not_attributed_effect" }[];
  currencies: { currency: "CHF" | "EUR"; selected_count: number; valued_count: number; unavailable_count: number; summed_projected_gross_minor: null }[];
  basis: "explicit_retained_scenario_comparison"; confidence: "conditional_unvalidated_scenarios"; summed_projected_gross_minor: null;
  validated_prediction: false; causal_effect_confirmed: false; action_executed: false; full_institute_scenario_cohort: false;
};
export type RevenueScenarioDeclaration = { assumptions: RevenueAssumptions; reason: string; idempotency_key: string };
export function validRevenueScenarioDeclaration(v: unknown): v is RevenueScenarioDeclaration {
  return keys(v, "assumptions reason idempotency_key") && validRevenueAssumptions(v.assumptions) && text(v.reason, 240)
    && Array.from(v.reason).length >= 3 && text(v.idempotency_key, 120);
}
export function matchesRevenueScenarioReceipt(e: RevenueScenarioEnvelope, terms: RevenueScenarioDeclaration, actor: string) {
  const o = e.original, a = o.assumptions, b = terms.assumptions;
  return o.actor_id === actor && o.reason === terms.reason && o.idempotency_key === terms.idempotency_key
    && a.model === b.model && a.currency === b.currency && a.activity_fraction.numerator === b.activity_fraction.numerator
    && a.activity_fraction.denominator === b.activity_fraction.denominator
    && (["observed_start", "observed_end", "projected_start", "projected_end"] as const).every(k => instant(a[k]) === instant(b[k]));
}
export type RevenueScenarioAudit = { institute_id: string; captured_at: string; offset: number; limit: number; total: number; originals: RevenueScenarioEnvelope[];
  full_original_cohort_verified: true; complete_sales_history: false; action_executed: false };
const keys = (v: unknown, names: string): v is Record<string, unknown> => !!v && typeof v === "object" && !Array.isArray(v) && Object.keys(v).sort().join(" ") === names.split(" ").sort().join(" ");
const text = (v: unknown, max: number): v is string => typeof v === "string" && !!v && v.trim() === v && Array.from(v).length <= max;
const unsigned = (v: unknown): v is string => typeof v === "string" && /^(0|[1-9][0-9]{0,29})$/.test(v);
export function validRevenueAssumptions(v: unknown): v is RevenueAssumptions {
  if (!keys(v, "model observed_start observed_end projected_start projected_end currency activity_fraction") || v.model !== "constant_recorded_gross_rate_v1"
    || !["CHF", "EUR"].includes(v.currency as string) || !keys(v.activity_fraction, "numerator denominator")
    || !unsigned(v.activity_fraction.numerator) || !unsigned(v.activity_fraction.denominator) || BigInt(v.activity_fraction.denominator) === 0n
    || BigInt(v.activity_fraction.numerator) > BigInt(v.activity_fraction.denominator)) return false;
  const times = [v.observed_start, v.observed_end, v.projected_start, v.projected_end].map(instant);
  return times.every(t => t !== undefined) && times[0]! < times[1]! && times[1]! <= times[2]! && times[2]! < times[3]!;
}
// Python ensure_ascii canonical JSON: preserve original datetime spellings.
function canonical(v: unknown): string {
  if (Array.isArray(v)) return `[${v.map(canonical).join(",")}]`;
  if (v !== null && typeof v === "object") return `{${Object.keys(v).sort().map(k => `${canonical(k)}:${canonical((v as Record<string, unknown>)[k])}`).join(",")}}`;
  const result = JSON.stringify(v);
  if (result === undefined) throw new Error("Unsupported original JSON");
  return result.replace(/[\u007f-\uffff]/g, c => `\\u${c.charCodeAt(0).toString(16).padStart(4, "0")}`);
}
export async function revenueOriginalFingerprint(value: unknown) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(canonical(value)));
  return Array.from(new Uint8Array(digest), b => b.toString(16).padStart(2, "0")).join("");
}
function gcd(a: bigint, b: bigint): bigint { while (b) { const rest = a % b; a = b; b = rest; } return a; }
export function validRevenueScenarioSelection(v: unknown): v is RevenueScenarioSelection {
  if (!keys(v, "baseline alternatives") || !Array.isArray(v.alternatives) || v.alternatives.length < 1 || v.alternatives.length > 19) return false;
  const refs = [v.baseline, ...v.alternatives];
  return refs.every(r => keys(r, "original_id fingerprint") && text(r.original_id, 80) && typeof r.fingerprint === "string" && /^[a-f0-9]{64}$/.test(r.fingerprint))
    && new Set(refs.map(r => r.original_id)).size === refs.length;
}
function stable(v: unknown): string { return canonical(v); }
function aggregateTerms(o: RevenueScenarioOriginal) {
  const { window, ...rest } = o.evidence;
  return { ...rest, window: { institute_id: window.institute_id, start: String(instant(window.start)), end: String(instant(window.end)) } };
}
export async function validRevenueScenarioComparison(v: unknown, institute: string, selection: RevenueScenarioSelection): Promise<boolean> {
  if (!validRevenueScenarioSelection(selection) || !keys(v, "institute_id captured_at baseline_original_id selected_count variants currencies basis confidence summed_projected_gross_minor validated_prediction causal_effect_confirmed action_executed full_institute_scenario_cohort")
    || v.institute_id !== institute || v.baseline_original_id !== selection.baseline.original_id || v.basis !== "explicit_retained_scenario_comparison"
    || v.confidence !== "conditional_unvalidated_scenarios" || v.summed_projected_gross_minor !== null || v.validated_prediction !== false
    || v.causal_effect_confirmed !== false || v.action_executed !== false || v.full_institute_scenario_cohort !== false || !Array.isArray(v.variants) || !Array.isArray(v.currencies)) return false;
  const refs = [selection.baseline, ...selection.alternatives], capture = instant(v.captured_at);
  if (capture === undefined || v.selected_count !== refs.length || v.variants.length !== refs.length) return false;
  for (let i = 0; i < refs.length; i++) {
    const item = v.variants[i];
    if (!keys(item, "original is_baseline same_source_capture same_recorded_billing_aggregates difference_from_baseline_minor difference_unavailable_reason difference_basis")
      || !await validRevenueScenarioEnvelope(item.original, institute)) return false;
    const e = item.original as RevenueScenarioEnvelope;
    if (e.original.id !== refs[i].original_id || e.fingerprint !== refs[i].fingerprint || instant(e.original.created_at)! > capture
      || item.is_baseline !== (i === 0) || item.difference_basis !== "comparison_only_not_attributed_effect") return false;
  }
  const variants = v.variants as RevenueScenarioComparison["variants"], baseline = variants[0].original.original, b = baseline.assumptions;
  const groups = new Map<string, { currency: string; selected_count: number; valued_count: number; unavailable_count: number; summed_projected_gross_minor: null }>();
  for (const item of variants) {
    const o = item.original.original, a = o.assumptions;
    const reason = a.currency !== b.currency ? "currency_difference" : a.model !== b.model ? "model_difference"
      : instant(a.observed_start) !== instant(b.observed_start) || instant(a.observed_end) !== instant(b.observed_end) ? "observed_period_difference"
      : instant(a.projected_start) !== instant(b.projected_start) || instant(a.projected_end) !== instant(b.projected_end) ? "projected_period_difference"
      : !o.projected_gross_minor || !baseline.projected_gross_minor ? "unavailable_projection" : null;
    if (item.difference_unavailable_reason !== reason || item.same_source_capture !== (instant(o.evidence.window.captured_at) === instant(baseline.evidence.window.captured_at))
      || item.same_recorded_billing_aggregates !== (stable(aggregateTerms(o)) === stable(aggregateTerms(baseline)))) return false;
    if (reason) { if (item.difference_from_baseline_minor !== null) return false; }
    else {
      const x = o.projected_gross_minor!, y = baseline.projected_gross_minor!, n = BigInt(x.numerator)*BigInt(y.denominator)-BigInt(y.numerator)*BigInt(x.denominator), d = BigInt(x.denominator)*BigInt(y.denominator), divisor = gcd(n < 0n ? -n : n, d);
      if (!keys(item.difference_from_baseline_minor, "numerator denominator") || item.difference_from_baseline_minor.numerator !== String(n/divisor) || item.difference_from_baseline_minor.denominator !== String(d/divisor)) return false;
    }
    const group = groups.get(a.currency) || { currency: a.currency, selected_count: 0, valued_count: 0, unavailable_count: 0, summed_projected_gross_minor: null };
    group.selected_count++; if (o.projected_gross_minor) group.valued_count++; else group.unavailable_count++; groups.set(a.currency, group);
  }
  return stable(v.currencies) === stable([...groups.values()].sort((a, b) => a.currency.localeCompare(b.currency)));
}
export async function validRevenueScenarioEnvelope(v: unknown, institute: string): Promise<boolean> {
  if (!keys(v, "original fingerprint") || typeof v.fingerprint !== "string" || !/^[a-f0-9]{64}$/.test(v.fingerprint)
    || !keys(v.original, "institute_id actor_id assumptions evidence basis projected_gross_minor confidence unavailable_reason validated_prediction action_executed id reason idempotency_key created_at retained")) return false;
  const o = v.original;
  if (o.institute_id !== institute || !text(o.id, 80) || !text(o.actor_id, 160) || /[\x00-\x1f]/.test(o.actor_id) || !text(o.reason, 240) || Array.from(o.reason).length < 3
    || !text(o.idempotency_key, 120) || !validRevenueAssumptions(o.assumptions) || o.basis !== "explicit_constant_historical_rate_scenario"
    || o.confidence !== "conditional_unvalidated_scenario" || o.retained !== true || o.validated_prediction !== false || o.action_executed !== false) return false;
  const a = o.assumptions, captured = instant(o.created_at);
  if (!validRevenueBilling(o.evidence, institute, { start: a.observed_start, end: a.observed_end }) || captured === undefined
    || instant(o.evidence.window.captured_at) !== captured || captured > instant(a.projected_start)!) return false;
  const group = o.evidence.ticket_amounts.find(g => g.currency === a.currency);
  const reason = o.evidence.ticket_amounts.some(g => g.currency === null) ? "unknown_currency" : o.evidence.institute_undated_paid_tickets ? "undated_paid_tickets"
    : !group ? "no_selected_currency" : group.complete_gross_minor === null ? "uncertain_amounts" : null;
  if (o.unavailable_reason !== reason) return false;
  if (reason !== null) { if (o.projected_gross_minor !== null) return false; }
  else {
    if (!keys(o.projected_gross_minor, "numerator denominator")) return false;
    const n = BigInt(group!.complete_gross_minor!) * (instant(a.projected_end)! - instant(a.projected_start)!) * BigInt(a.activity_fraction.numerator);
    const d = (instant(a.observed_end)! - instant(a.observed_start)!) * BigInt(a.activity_fraction.denominator), divisor = gcd(n, d);
    if (o.projected_gross_minor.numerator !== String(n/divisor) || o.projected_gross_minor.denominator !== String(d/divisor)) return false;
  }
  try { return await revenueOriginalFingerprint(o) === v.fingerprint; } catch { return false; }
}
export async function validRevenueScenarioAudit(v: unknown, institute: string, offset: number): Promise<boolean> {
  if (!Number.isSafeInteger(offset) || offset < 0) return false;
  if (!keys(v, "institute_id captured_at offset limit total originals full_original_cohort_verified complete_sales_history action_executed")
    || v.institute_id !== institute || v.offset !== offset || v.limit !== 20 || typeof v.total !== "number" || !Number.isSafeInteger(v.total) || v.total < 0
    || v.full_original_cohort_verified !== true || v.complete_sales_history !== false || v.action_executed !== false || !Array.isArray(v.originals)
    || v.originals.length !== Math.min(20, Math.max(0, v.total-offset))) return false;
  const capture = instant(v.captured_at); if (capture === undefined) return false;
  if (!(await Promise.all(v.originals.map(o => validRevenueScenarioEnvelope(o, institute)))).every(Boolean)) return false;
  let previous: RevenueScenarioOriginal | undefined;
  for (const envelope of v.originals as RevenueScenarioEnvelope[]) {
    const o = envelope.original, at = instant(o.created_at)!;
    if (at > capture || previous && (at < instant(previous.created_at)! || at === instant(previous.created_at)! && o.id <= previous.id)) return false;
    previous = o;
  }
  return new Set((v.originals as RevenueScenarioEnvelope[]).map(e => e.original.id)).size === v.originals.length
    && new Set((v.originals as RevenueScenarioEnvelope[]).map(e => e.original.idempotency_key)).size === v.originals.length;
}
