import { certificationInstant as instant, certificationDate, validRevokeTerms, type RevokeTerms } from "./certification-utils";
import { instituteBoundary } from "./institute-calendar";
type Currency = "CHF" | "EUR";
type Rounding = "half_up" | "half_even" | "down";
export type CommissionRuleTerms = RevokeTerms & { employee_id: string; title: string; basis: "closed_attributed_line_gross"; currency: Currency;
  category: string; service_id: string | null; rate_basis_points: number; rounding: Rounding; first_day: string; last_day: string };
export type RuleCancellation = RevokeTerms & { id: string; institute_id: string; rule_id: string; actor_id: string; created_at: string };
export type CommissionRule = CommissionRuleTerms & { id: string; institute_id: string; actor_id: string; created_at: string; timezone: string;
  period_start: string; period_end: string; cancellation: RuleCancellation | null };
export type CommissionPolicy = Pick<CommissionRule, "employee_id" | "basis" | "currency" | "category" | "service_id" | "rate_basis_points" | "rounding" | "period_start" | "period_end">;
export type CommissionSource = { institute_id: string; ticket_id: string; line_id: string; employee_id: string; service_id: string; category: string;
  currency: Currency; quantity: number; gross_minor: string; arrival_at: string; paid_at: string; captured_at: string };
export type CommissionCalculation = { terms: CommissionPolicy; source: CommissionSource; unrounded_numerator: string; rounding_remainder: number; amount_minor: string };
export type CommissionTerms = RevokeTerms & { rule_id: string; line_id: string };
export type CommissionCancellation = RevokeTerms & { id: string; institute_id: string; commission_id: string; actor_id: string; created_at: string };
export type Commission = CommissionTerms & { id: string; institute_id: string; employee_id: string; ticket_id: string; actor_id: string; created_at: string;
  rule_capture: CommissionRule; calculation: CommissionCalculation; cancellation: CommissionCancellation | null };
type Page = { offset: number; limit: number; total: number };
export type CommissionRulePage = { institute_id: string; employee_id: string; generated_at: string; page: Page; rows: CommissionRule[] };
export type CommissionPage = { institute_id: string; employee_id: string; generated_at: string; page: Page; rows: Commission[] };
export type RuleIntent = { type: "create"; terms: CommissionRuleTerms } | { type: "cancel"; original: CommissionRule; terms: RevokeTerms };
export type CommissionIntent = { type: "create"; terms: CommissionTerms } | { type: "cancel"; original: Commission; terms: RevokeTerms };
export const commissionStates = ["recorded", "cancelled", "future_recording", "future_cancellation"] as const;
export type CommissionState = typeof commissionStates[number];
type Counts = Record<CommissionState, number>;
export type CommissionDay = { institute_id: string; employee_id: string; day: string; timezone: string; start: string; end: string; generated_at: string;
  basis: "commission_recorded_at"; page: Page; rows: { original: Commission; state: CommissionState }[]; counts: Counts;
  currencies: { currency: Currency; counts: Counts; amounts_minor: Record<CommissionState, string> }[]; complete_entitlement: false; payable_total: null };
const text = (v: unknown, max = 80): v is string => typeof v === "string" && !!v && v.trim() === v && v.length <= max;
const count = (v: unknown): v is number => Number.isSafeInteger(v) && (v as number) >= 0;
export function commissionMinor(v: unknown, max = 30): bigint | undefined {
  if (typeof v === "string" && v.length <= max && /^(0|[1-9]\d*)$/.test(v)) return BigInt(v);
}
export function validCommissionRuleTerms(v: unknown): v is CommissionRuleTerms {
  const r = v as CommissionRuleTerms;
  return validRevokeTerms(r) && text(r.employee_id) && text(r.title, 120) && r.basis === "closed_attributed_line_gross"
    && ["CHF", "EUR"].includes(r.currency) && text(r.category, 40) && (r.service_id === null || text(r.service_id))
    && count(r.rate_basis_points) && r.rate_basis_points <= 10000 && ["half_up", "half_even", "down"].includes(r.rounding)
    && certificationDate(r.first_day) && certificationDate(r.last_day) && r.last_day >= r.first_day;
}
export function validRuleCancellation(v: unknown, institute: string, rule?: string): v is RuleCancellation {
  const r = v as RuleCancellation;
  return validRevokeTerms(r) && text(r.id) && r.institute_id === institute && text(r.rule_id) && (!rule || r.rule_id === rule)
    && text(r.actor_id, 160) && instant(r.created_at) !== undefined;
}
export function validCommissionRule(v: unknown, institute: string, employee?: string): v is CommissionRule {
  const r = v as CommissionRule;
  if (!validCommissionRuleTerms(r) || r.institute_id !== institute || !text(r.id) || !text(r.actor_id, 160)
    || employee && r.employee_id !== employee || !text(r.timezone) || instant(r.created_at) === undefined) return false;
  try {
    new Intl.DateTimeFormat("en", { timeZone: r.timezone });
    const next = (day: string) => new Date(Date.parse(`${day}T12:00:00Z`)+86400000).toISOString().slice(0, 10);
    const boundary = (day: string): number | undefined => instituteBoundary(day, 0, r.timezone) ?? instituteBoundary(next(day), 0, r.timezone);
    const from = boundary(r.first_day), until = boundary(next(r.last_day)), first = instant(r.period_start), last = instant(r.period_end);
    if (from === undefined || until === undefined || first === undefined || last === undefined || last <= first
      || first !== BigInt(from)*1000n || last !== BigInt(until)*1000n) return false;
  } catch { return false; }
  return r.cancellation === null || validRuleCancellation(r.cancellation, institute, r.id) && instant(r.cancellation.created_at)! >= instant(r.created_at)!;
}
const policyKeys = ["employee_id", "basis", "currency", "category", "service_id", "rate_basis_points", "rounding"] as const;
function samePolicy(a: CommissionPolicy, b: CommissionPolicy) {
  return policyKeys.every(k => a[k] === b[k]) && instant(a.period_start) === instant(b.period_start) && instant(a.period_end) === instant(b.period_end);
}
export function validCommissionCalculation(v: unknown, rule: CommissionRule, institute: string): v is CommissionCalculation {
  const r = v as CommissionCalculation, s = r?.source;
  if (!r?.terms || !s || !samePolicy(r.terms, rule) || s.institute_id !== institute || s.employee_id !== rule.employee_id
    || !text(s.ticket_id) || !text(s.line_id) || !text(s.service_id) || s.category !== rule.category || s.currency !== rule.currency
    || rule.service_id !== null && s.service_id !== rule.service_id || !count(s.quantity) || s.quantity < 1 || s.quantity > 2147483647) return false;
  const gross = commissionMinor(s.gross_minor, 10), first = instant(s.arrival_at), paid = instant(s.paid_at), captured = instant(s.captured_at);
  if (gross === undefined || first === undefined || paid === undefined || captured === undefined || first > paid || paid > captured
    || paid < instant(rule.period_start)! || paid >= instant(rule.period_end)!) return false;
  const numerator = gross*BigInt(rule.rate_basis_points), quotient = numerator/10000n, remainder = numerator%10000n;
  const increment = rule.rounding === "half_up" && remainder >= 5000n || rule.rounding === "half_even" && (remainder > 5000n || remainder === 5000n && quotient%2n === 1n);
  return commissionMinor(r.unrounded_numerator) === numerator && r.rounding_remainder === Number(remainder)
    && commissionMinor(r.amount_minor, 10) === quotient+(increment ? 1n : 0n);
}
export function validCommissionTerms(v: unknown): v is CommissionTerms {
  const r = v as CommissionTerms;
  return validRevokeTerms(r) && text(r.rule_id) && text(r.line_id);
}
export function validCommissionCancellation(v: unknown, institute: string, commission?: string): v is CommissionCancellation {
  const r = v as CommissionCancellation;
  return validRevokeTerms(r) && text(r.id) && r.institute_id === institute && text(r.commission_id)
    && (!commission || r.commission_id === commission) && text(r.actor_id, 160) && instant(r.created_at) !== undefined;
}
export function validCommission(v: unknown, institute: string, employee?: string): v is Commission {
  const r = v as Commission, rule = r?.rule_capture;
  if (!validCommissionTerms(r) || r.institute_id !== institute || !text(r.id) || !text(r.employee_id) || !text(r.ticket_id)
    || !text(r.actor_id, 160) || employee && r.employee_id !== employee || !validCommissionRule(rule, institute, r.employee_id)
    || rule.id !== r.rule_id || rule.cancellation !== null || !validCommissionCalculation(r.calculation, rule, institute)
    || r.calculation.source.line_id !== r.line_id || r.calculation.source.ticket_id !== r.ticket_id) return false;
  const recorded = instant(r.created_at);
  return recorded !== undefined && recorded >= instant(rule.created_at)! && recorded === instant(r.calculation.source.captured_at)
    && (r.cancellation === null || validCommissionCancellation(r.cancellation, institute, r.id) && instant(r.cancellation.created_at)! >= recorded);
}
export const matchesCommissionRule = (r: CommissionRule, t: CommissionRuleTerms, actor: string) => r.actor_id === actor
  && (["employee_id", "title", "basis", "currency", "category", "service_id", "rate_basis_points", "rounding", "first_day", "last_day", "reason", "idempotency_key"] as const).every(k => r[k] === t[k]);
export const matchesCommission = (r: Commission, t: CommissionTerms, actor: string) => r.actor_id === actor
  && r.rule_id === t.rule_id && r.line_id === t.line_id && r.reason === t.reason && r.idempotency_key === t.idempotency_key;
export function sameCommissionRuleOriginal(a: CommissionRule, b: CommissionRule) {
  return a.id === b.id && a.institute_id === b.institute_id && matchesCommissionRule(a, b, b.actor_id) && a.timezone === b.timezone
    && instant(a.created_at) === instant(b.created_at) && samePolicy(a, b);
}
export function sameCommissionOriginal(a: Commission, b: Commission) {
  const s = a.calculation.source, t = b.calculation.source;
  return a.id === b.id && a.institute_id === b.institute_id && a.employee_id === b.employee_id && a.ticket_id === b.ticket_id
    && matchesCommission(a, b, b.actor_id) && instant(a.created_at) === instant(b.created_at) && sameCommissionRuleOriginal(a.rule_capture, b.rule_capture)
    && samePolicy(a.calculation.terms, b.calculation.terms)
    && (["institute_id", "ticket_id", "line_id", "employee_id", "service_id", "category", "currency", "quantity", "gross_minor"] as const).every(k => s[k] === t[k])
    && (["arrival_at", "paid_at", "captured_at"] as const).every(k => instant(s[k]) === instant(t[k]))
    && a.calculation.unrounded_numerator === b.calculation.unrounded_numerator && a.calculation.rounding_remainder === b.calculation.rounding_remainder
    && a.calculation.amount_minor === b.calculation.amount_minor;
}
export function validCommissionRuleIntent(v: unknown, institute: string): v is RuleIntent {
  const r = v as RuleIntent;
  return !!r && (r.type === "create" ? validCommissionRuleTerms(r.terms) : r.type === "cancel" && validCommissionRule(r.original, institute)
    && r.original.cancellation === null && validRevokeTerms(r.terms));
}
export function validCommissionIntent(v: unknown, institute: string): v is CommissionIntent {
  const r = v as CommissionIntent;
  return !!r && (r.type === "create" ? validCommissionTerms(r.terms) : r.type === "cancel" && validCommission(r.original, institute)
    && r.original.cancellation === null && validRevokeTerms(r.terms));
}
function page(p: Page, rows: unknown[], offset: number) {
  return count(offset) && offset%20 === 0 && !!p && p.offset === offset && p.limit === 20 && count(p.total)
    && Array.isArray(rows) && rows.length === Math.min(20, Math.max(0, p.total-offset));
}
function uniqueActive(rows: Commission[]) {
  const active = rows.filter(r => r.cancellation === null);
  return new Set(active.map(r => r.line_id)).size === active.length;
}
export function validCommissionRulePage(v: unknown, institute: string, employee: string, offset: number): v is CommissionRulePage {
  const r = v as CommissionRulePage;
  return !!r && r.institute_id === institute && r.employee_id === employee && instant(r.generated_at) !== undefined && page(r.page, r.rows, offset)
    && r.rows.every(s => validCommissionRule(s, institute, employee)) && new Set(r.rows.map(s => s.id)).size === r.rows.length;
}
export function validCommissionPage(v: unknown, institute: string, employee: string, offset: number): v is CommissionPage {
  const r = v as CommissionPage;
  return !!r && r.institute_id === institute && r.employee_id === employee && instant(r.generated_at) !== undefined && page(r.page, r.rows, offset)
    && r.rows.every(s => validCommission(s, institute, employee)) && new Set(r.rows.map(s => s.id)).size === r.rows.length && uniqueActive(r.rows);
}
export function commissionState(r: Commission, now: bigint): CommissionState {
  return instant(r.created_at)! > now ? "future_recording" : r.cancellation ? instant(r.cancellation.created_at)! > now ? "future_cancellation" : "cancelled" : "recorded";
}
const stateMap = (v: object) => !!v && Object.keys(v).length === commissionStates.length && commissionStates.every(k => Object.prototype.hasOwnProperty.call(v, k));
export function validCommissionDay(v: unknown, institute: string, employee: string, day: string, start: string, end: string, zone: string, offset: number): v is CommissionDay {
  const r = v as CommissionDay, now = instant(r?.generated_at), from = instant(start), until = instant(end);
  if (!r || r.institute_id !== institute || r.employee_id !== employee || r.day !== day || !certificationDate(day) || r.timezone !== zone
    || from === undefined || until === undefined || until < from || instant(r.start) !== from || instant(r.end) !== until || now === undefined
    || r.basis !== "commission_recorded_at" || r.complete_entitlement !== false || r.payable_total !== null || !page(r.page, r.rows, offset)
    || !stateMap(r.counts) || !commissionStates.every(k => count(r.counts[k])) || commissionStates.reduce((n, k) => n+r.counts[k], 0) !== r.page.total
    || !Array.isArray(r.currencies) || r.currencies.length > 2 || new Set(r.currencies.map(c => c?.currency)).size !== r.currencies.length) return false;
  const seen = Object.fromEntries(commissionStates.map(k => [k, 0])) as Counts;
  const groups = new Map<Currency, { counts: Counts; sums: Record<CommissionState, bigint> }>();
  for (const group of r.currencies) {
    if (!group || !["CHF", "EUR"].includes(group.currency) || !stateMap(group.counts) || !stateMap(group.amounts_minor)
      || !commissionStates.every(k => count(group.counts[k]) && commissionMinor(group.amounts_minor[k]) !== undefined
        && commissionMinor(group.amounts_minor[k])! <= BigInt(group.counts[k])*9999999999n
        && (group.counts[k] !== 0 || group.amounts_minor[k] === "0")) || commissionStates.reduce((n, k) => n+group.counts[k], 0) === 0) return false;
  }
  if (!commissionStates.every(k => r.currencies.reduce((n, c) => n+c.counts[k], 0) === r.counts[k])) return false;
  for (const row of r.rows) {
    if (!row || !validCommission(row.original, institute, employee) || !commissionStates.includes(row.state) || commissionState(row.original, now) !== row.state
      || instant(row.original.created_at)! < from || instant(row.original.created_at)! >= until) return false;
    seen[row.state]++;
    const currency = row.original.calculation.source.currency;
    if (!groups.has(currency)) groups.set(currency, { counts: Object.fromEntries(commissionStates.map(k => [k, 0])) as Counts,
      sums: Object.fromEntries(commissionStates.map(k => [k, 0n])) as Record<CommissionState, bigint> });
    const g = groups.get(currency)!; g.counts[row.state]++; g.sums[row.state] += BigInt(row.original.calculation.amount_minor);
  }
  const complete = offset === 0 && r.page.total <= 20;
  if (new Set(r.rows.map(s => s.original.id)).size !== r.rows.length || !uniqueActive(r.rows.map(s => s.original))
    || !commissionStates.every(k => seen[k] <= r.counts[k] && (!complete || seen[k] === r.counts[k]))) return false;
  if ([...groups.keys()].some(currency => !r.currencies.some(c => c.currency === currency))) return false;
  return r.currencies.every(c => commissionStates.every(k => {
    const observed = groups.get(c.currency), amount = commissionMinor(c.amounts_minor[k])!;
    return (observed?.counts[k] || 0) <= c.counts[k] && (observed?.sums[k] || 0n) <= amount
      && (!complete || (observed?.counts[k] || 0) === c.counts[k] && (observed?.sums[k] || 0n) === amount);
  }));
}
