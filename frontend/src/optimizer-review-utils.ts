import { certificationInstant as instant } from "./certification-utils";
import { revenueOriginalFingerprint as hash } from "./revenue-scenario-utils";
import { validWaitlistMatching, type WaitlistMatching, type WaitlistMatchingSelection, type WaitlistReview } from "./waitlist-matching-utils";
import { optimizerFactors, optimizerBases, validOptimizerPolicyEnvelope, type OptimizerPolicyEnvelope, type OptimizerRule } from "./optimizer-policy-utils";
type Option = WaitlistReview["options"][number];
type Ratio = { numerator: string; denominator: string };
type Observation = { factor: OptimizerRule["factor"]; state: "known" | "unknown"; value: Ratio | null; reference: string | null; observed_at: string | null; reason: string };
type Raw = { factor: OptimizerRule["factor"]; basis: string; quantity: string | null; denominator: string | null; currency: string | null;
  price_mode: string | null; reference: string | null; observed_at: string | null; reason: string };
type Normalized = { rule: OptimizerRule; source: Raw; observation: Observation; saturated: "yes" | "no" | "not_computed";
  meaning: "explicit_policy_normalization_not_quote_profit_or_prediction" };
type Constraint = { id: string; state: "satisfied"; reference: string; observed_at: string; reason: string };
type Contribution = { factor: OptimizerRule["factor"]; direction: "reward" | "penalty"; weight: Ratio; observation: Observation;
  state: "included" | "disabled_by_policy" | "unavailable"; contribution: Ratio | null };
type Scored = { option: Option; score: Ratio | null; rank: number | null; state: "conditional_scored" | "score_unavailable";
  reasons: string[]; constraints: Constraint[]; contributions: Contribution[] };
export type OptimizerReviewSelection = WaitlistMatchingSelection & { policyOriginal: OptimizerPolicyEnvelope };
export type OptimizerReview = { institute_id: string; captured_at: string; policy_original: OptimizerPolicyEnvelope; source: WaitlistMatching;
  catalog: { service_id: string; price_member: string | null; price_passage: string | null; currency: "not_recorded"; meaning: "catalog_reference_not_customer_quote_or_profit" } | null;
  proofs: { option: Option; containing_employee_window: { start: string; end: string }; factors: Normalized[] }[];
  review: { institute_id: string; captured_at: string; source: WaitlistReview; policy: { institute_id: string; id: string; captured_at: string;
    reason: string; weights: { factor: OptimizerRule["factor"]; value: Ratio }[]; scale: "explicit_normalized_unit_interval" };
    options: Scored[]; ranking: "complete" | "incomplete_evidence" | "no_admissible_options";
    confidence: "conditional_recorded_capacity_and_explicit_policy"; action: "human_review_then_revalidate_no_booking_or_contact" } | null;
  action: "human_review_then_revalidate_no_booking_or_contact" };
const core = [
  ["captured_demand_review", "source.demand", "Explicit human constraints review is confirmed"],
  ["captured_duration_match", "source.capture.service", "Declared and captured service durations agree"],
  ["captured_customer_window", "source.demand.availability", "Option fits declared customer availability and capture clock"],
  ["captured_employee_window", "source.capture.employees", "Option fits a known captured employee window and restriction"],
  ["captured_skills_match", "source.capture.service", "Captured employee qualification satisfies service requirements"],
  ["captured_distinct_resource_fit", "source.capture.resources", "Complete distinct captured resources fit without reservation conflicts"],
  ["captured_customer_conflicts", "source.capture.customer_blockers", "No captured customer occupation overlaps this option"],
  ["captured_queue_known", "source.capture.queue_capacity", "Core queue capacity is known and virtual blockers are applied"],
] as const;
const keys = (v: unknown, names: string): v is Record<string, any> => !!v && typeof v === "object" && !Array.isArray(v) && Object.keys(v).sort().join(" ") === names.split(" ").sort().join(" ");
const time = (a: unknown, b: unknown) => instant(a) !== undefined && instant(a) === instant(b);
const text = (v: unknown): v is string => typeof v === "string" && v === v.trim() && Array.from(v).length >= 3 && Array.from(v).length <= 240;
const same = async (a: unknown, b: unknown) => await hash(a) === await hash(b);
type Fraction = [bigint, bigint];
function gcd(a: bigint, b: bigint): bigint { a = a < 0n ? -a : a; while (b) [a, b] = [b, a % b]; return a; }
function reduced(n: bigint, d: bigint): Fraction { const g = gcd(n, d); return [n/g, d/g]; }
function exact(v: unknown, f: Fraction, signed = false) {
  const [n, d] = reduced(...f);
  return keys(v, "numerator denominator") && typeof v.numerator === "string" && typeof v.denominator === "string"
    && v.numerator.length <= (signed ? 700 : 40) && v.denominator.length <= (signed ? 700 : 40)
    && v.numerator === String(n) && v.denominator === String(d);
}
function cmpText(a: string, b: string): number { const x = Array.from(a), y = Array.from(b); for (let i = 0; i < Math.min(x.length, y.length); i++) { const d = x[i].codePointAt(0)!-y[i].codePointAt(0)!; if (d) return d; } return x.length-y.length; }
function identity(a: Option, b: Option) { for (const k of ["start", "end"] as const) { const x = instant(a[k])!, y = instant(b[k])!; if (x !== y) return x < y ? -1 : 1; }
  const employee = cmpText(a.employee_id, b.employee_id); if (employee) return employee;
  const x = [...a.resource_ids].sort(cmpText), y = [...b.resource_ids].sort(cmpText); for (let i = 0; i < Math.min(x.length, y.length); i++) { const d = cmpText(x[i], y[i]); if (d) return d; } return x.length-y.length;
}

export async function validOptimizerReview(value: unknown, institute: string, selection: OptimizerReviewSelection): Promise<boolean> {
  try {
    if (!keys(value, "institute_id captured_at policy_original source catalog proofs review action") || value.institute_id !== institute
      || value.action !== "human_review_then_revalidate_no_booking_or_contact" || !await validOptimizerPolicyEnvelope(selection.policyOriginal, institute)
      || !await validOptimizerPolicyEnvelope(value.policy_original, institute) || !await same(value.policy_original, selection.policyOriginal)
      || !await validWaitlistMatching(value.source, institute, selection) || !time(value.captured_at, value.source.captured_at)
      || instant(value.policy_original.original.created_at)! > instant(value.captured_at)! || !Array.isArray(value.proofs)) return false;
    const v = value as OptimizerReview, source = v.source.review, original = v.policy_original.original;
    if (!source) return v.review === null && v.catalog === null && v.proofs.length === 0;
    if (!keys(v.catalog, "service_id price_member price_passage currency meaning") || v.catalog.service_id !== source.demand.service_id
      || v.catalog.currency !== "not_recorded" || v.catalog.meaning !== "catalog_reference_not_customer_quote_or_profit"
      || ![v.catalog.price_member, v.catalog.price_passage].every(p => p === null || typeof p === "string")
      || !keys(v.review, "institute_id captured_at source policy options ranking confidence action") || v.review.institute_id !== institute
      || !time(v.review.captured_at, v.captured_at) || !await same(v.review.source, source)
      || v.review.confidence !== "conditional_recorded_capacity_and_explicit_policy" || v.review.action !== v.action
      || !keys(v.review.policy, "institute_id id captured_at reason weights scale") || v.review.policy.institute_id !== institute
      || v.review.policy.id !== original.id || !time(v.review.policy.captured_at, original.created_at) || v.review.policy.reason !== original.reason
      || v.review.policy.scale !== "explicit_normalized_unit_interval" || !await same(v.review.policy.weights,
        optimizerFactors.map(f => ({ factor: f, value: original.terms.rules.find(r => r.factor === f)!.weight })))
      || !Array.isArray(v.review.options) || v.proofs.length !== source.options.length || v.review.options.length !== source.options.length) return false;
    const expected: { option: Option; score: Fraction | null }[] = [];
    for (let i = 0; i < v.proofs.length; i++) {
      const p = v.proofs[i], option = source.options[i];
      if (!keys(p, "option containing_employee_window factors") || !await same(p.option, option) || !keys(p.containing_employee_window, "start end")
        || !Array.isArray(p.factors) || p.factors.length !== 8) return false;
      const window = source.capture.employees.find(e => e.employee_id === option.employee_id)?.windows.find(w => instant(w.start)! <= instant(option.start)! && instant(option.end)! <= instant(w.end)!);
      if (!window || !await same(p.containing_employee_window, window)) return false;
      const row = v.review.options.find(o => identity(o.option, option) === 0);
      if (!row || !keys(row, "option score rank state reasons constraints contributions") || !await same(row.option, option)
        || !Array.isArray(row.contributions) || row.contributions.length !== 8 || !Array.isArray(row.constraints) || row.constraints.length !== core.length) return false;
      let total: Fraction = [0n, 1n], unavailable = false; const reasons: string[] = [];
      for (let j = 0; j < optimizerFactors.length; j++) {
        const f = optimizerFactors[j], normalized = p.factors[j], rule = original.terms.rules.find(r => r.factor === f)!;
        if (!keys(normalized, "rule source observation saturated meaning") || !await same(normalized.rule, rule)
          || normalized.meaning !== "explicit_policy_normalization_not_quote_profit_or_prediction"
          || !keys(normalized.source, "factor basis quantity denominator currency price_mode reference observed_at reason")
          || !keys(normalized.observation, "factor state value reference observed_at reason")) return false;
        const raw = normalized.source, obs = normalized.observation;
        if (raw.factor !== f || raw.basis !== optimizerBases[f] || raw.currency !== null || raw.price_mode !== null || !text(raw.reason)
          || obs.factor !== f || obs.reason !== raw.reason) return false;
        let quantity: bigint | null = null, denominator: bigint | null = null, ref: string | null = null, fraction: Fraction | null = null;
        if (f === "utilization_score") { quantity = instant(option.end)!-instant(option.start)!; denominator = instant(window.end)!-instant(window.start)!; ref = "proofs.containing_employee_window"; }
        else if (f === "idle_gap_penalty") { quantity = instant(option.start)!-instant(v.captured_at)!; ref = "source.captured_at"; }
        else if (f === "resource_conflict_penalty") { quantity = 0n; ref = "source.review.capture.resources"; }
        if (raw.quantity !== (quantity === null ? null : String(quantity)) || raw.denominator !== (denominator === null ? null : String(denominator))
          || raw.reference !== ref || (quantity === null ? raw.observed_at !== null : !time(raw.observed_at, v.captured_at))) return false;
        let saturated = false;
        if (quantity !== null && (rule.basis !== "disabled" || f === "resource_conflict_penalty")) {
          fraction = reduced(quantity, denominator ?? (f === "idle_gap_penalty" ? BigInt(rule.ceiling!) : 1n));
          saturated = fraction[0] > fraction[1]; if (saturated) fraction = [1n, 1n];
        }
        if (fraction === null ? obs.state !== "unknown" || obs.value !== null || obs.reference !== null || obs.observed_at !== null || normalized.saturated !== "not_computed"
          : obs.state !== "known" || !exact(obs.value, fraction) || obs.reference !== ref || !time(obs.observed_at, v.captured_at) || normalized.saturated !== (saturated ? "yes" : "no")) return false;
        const part = row.contributions[j], weight: Fraction = [BigInt(rule.weight.numerator), BigInt(rule.weight.denominator)], penalty = j >= 5;
        if (!keys(part, "factor direction weight observation state contribution") || part.factor !== f || part.direction !== (penalty ? "penalty" : "reward")
          || !await same(part.weight, rule.weight) || !await same(part.observation, obs)) return false;
        if (weight[0] === 0n) { if (part.state !== "disabled_by_policy" || part.contribution !== null) return false; reasons.push(`${f}: explicitly disabled by policy; ${obs.reason}`); }
        else if (!fraction) { if (part.state !== "unavailable" || part.contribution !== null) return false; unavailable = true; reasons.push(`${f}: weighted evidence unavailable; ${obs.reason}`); }
        else { const c = reduced(weight[0]*fraction[0]*(penalty ? -1n : 1n), weight[1]*fraction[1]);
          if (part.state !== "included" || !exact(part.contribution, c, true)) return false;
          total = reduced(total[0]*c[1]+c[0]*total[1], total[1]*c[1]); reasons.push(`${f}: ${c[0]}/${c[1]}; ${obs.reason}`); }
      }
      for (let j = 0; j < core.length; j++) { const c = row.constraints[j], [id, reference, reason] = core[j];
        if (!keys(c, "id state reference observed_at reason") || c.id !== id || c.state !== "satisfied" || c.reference !== reference || c.reason !== reason || !time(c.observed_at, v.captured_at)) return false;
        reasons.push(`constraint ${id}: satisfied; ${reason}`); }
      if (!await same(row.reasons, reasons) || row.state !== (unavailable ? "score_unavailable" : "conditional_scored") || (unavailable ? row.score !== null : !exact(row.score, total, true))) return false;
      expected.push({ option, score: unavailable ? null : total });
    }
    const incomplete = expected.some(r => r.score === null), ranking = incomplete ? "incomplete_evidence" : expected.length ? "complete" : "no_admissible_options";
    if (v.review.ranking !== ranking) return false;
    expected.sort((a, b) => { if (!incomplete && a.score && b.score) { const d = a.score[0]*b.score[1]-b.score[0]*a.score[1]; if (d) return d > 0n ? -1 : 1; } return identity(a.option, b.option); });
    let rank = 0;
    for (let i = 0; i < expected.length; i++) { const row = v.review.options[i], e = expected[i];
      if (!await same(row.option, e.option)) return false;
      if (incomplete) { if (row.rank !== null) return false; }
      else { if (i === 0 || expected[i-1].score![0]*e.score![1] !== e.score![0]*expected[i-1].score![1]) rank = i+1; if (row.rank !== rank) return false; }
    }
    return true;
  } catch { return false; }
}
