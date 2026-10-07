import { certificationInstant as instant } from "./certification-utils";
import { validRevenueBilling, type RevenueBilling } from "./revenue-utils";
export type RevenueAssumptions = { model: "constant_recorded_gross_rate_v1"; observed_start: string; observed_end: string; projected_start: string; projected_end: string; currency: "CHF" | "EUR"; activity_fraction: { numerator: string; denominator: string } };
export type RevenueScenarioOriginal = { institute_id: string; actor_id: string; assumptions: RevenueAssumptions; evidence: RevenueBilling;
  basis: "explicit_constant_historical_rate_scenario"; projected_gross_minor: { numerator: string; denominator: string } | null;
  confidence: "conditional_unvalidated_scenario"; unavailable_reason: "unknown_currency" | "undated_paid_tickets" | "no_selected_currency" | "uncertain_amounts" | null;
  validated_prediction: false; action_executed: false; id: string; reason: string; idempotency_key: string; created_at: string; retained: true };
export type RevenueScenarioEnvelope = { original: RevenueScenarioOriginal; fingerprint: string };
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
