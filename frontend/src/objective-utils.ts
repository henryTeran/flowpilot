import { certificationDate, certificationInstant, validRevokeTerms, type RevokeTerms } from "./certification-utils";
import { instituteBoundary } from "./institute-calendar";
import { revenueCents } from "./employee-revenue-utils";
export type ObjectiveTerms = RevokeTerms & { employee_id: string; title: string; metric: "closed_attributed_gross" | "completed_sessions";
  currency: "CHF" | "EUR" | null; target: string; first_day: string; last_day: string };
export type ObjectiveCancellation = RevokeTerms & { id: string; institute_id: string; objective_id: string; actor_id: string; created_at: string };
export type Objective = ObjectiveTerms & { id: string; institute_id: string; actor_id: string; created_at: string; timezone: string;
  period_start: string; period_end: string; cancellation: ObjectiveCancellation | null };
export type ObjectiveProgress = { objective: Objective; period_state: "upcoming" | "active" | "ended" | "cancelled";
  known_value: string | null; value: string | null; achieved: boolean | null; source_count: number | null;
  missing_amount_sources: number | null; unknown_currency_sources: number | null; other_currency_sources: number | null };
export type ObjectivePage = { institute_id: string; employee_id: string; generated_at: string;
  page: { offset: number; limit: number; total: number }; rows: ObjectiveProgress[] };
const text = (v: unknown, max: number): v is string => typeof v === "string" && !!v && v.trim() === v && v.length <= max;
const count = (v: unknown): v is number => Number.isSafeInteger(v) && (v as number) >= 0;
export function objectiveCents(value: unknown) {
  if (typeof value !== "string" || value.length > 1000 || !/^\d+(?:\.\d+)?$/.test(value)) return;
  return revenueCents(value.includes(".") ? value.replace(/0+$/, "").replace(/\.$/, "") : value);
}
export function validObjectiveTerms(value: unknown): value is ObjectiveTerms {
  const r = value as ObjectiveTerms, target = objectiveCents(r?.target);
  if (!validRevokeTerms(r) || !text(r.employee_id, 80) || !text(r.title, 120) || target === undefined || target <= 0n
    || target >= 100000000000000000000n || !certificationDate(r.first_day) || !certificationDate(r.last_day) || r.last_day < r.first_day) return false;
  return r.metric === "closed_attributed_gross" ? r.currency === "CHF" || r.currency === "EUR"
    : r.metric === "completed_sessions" && r.currency === null && target % 100n === 0n;
}
export function validObjectiveCancellation(value: unknown, institute: string, objective?: string): value is ObjectiveCancellation {
  const r = value as ObjectiveCancellation;
  return validRevokeTerms(r) && r.institute_id === institute && text(r.id, 80) && text(r.objective_id, 80)
    && (!objective || objective === r.objective_id) && text(r.actor_id, 160) && certificationInstant(r.created_at) !== undefined;
}
export function validObjective(value: unknown, institute: string, employee?: string): value is Objective {
  const r = value as Objective;
  if (!validObjectiveTerms(r) || r.institute_id !== institute || employee && r.employee_id !== employee || !text(r.id, 80)
    || !text(r.actor_id, 160) || certificationInstant(r.created_at) === undefined || !text(r.timezone, 80)) return false;
  try {
    new Intl.DateTimeFormat("en", { timeZone: r.timezone });
    const start = certificationInstant(r.period_start), end = certificationInstant(r.period_end);
    const boundary = (day: string) => {
      const exact = instituteBoundary(day, 0, r.timezone);
      if (exact !== undefined) return exact;
      const next = new Date(Date.parse(`${day}T12:00:00Z`)+86400000).toISOString().slice(0, 10);
      return instituteBoundary(next, 0, r.timezone);
    };
    const nextLast = new Date(Date.parse(`${r.last_day}T12:00:00Z`)+86400000).toISOString().slice(0, 10);
    const from = boundary(r.first_day), until = boundary(nextLast);
    if (start === undefined || end === undefined || end <= start || from === undefined || until === undefined
      || start !== BigInt(from)*1000n || end !== BigInt(until)*1000n) return false;
  } catch { return false; }
  return r.cancellation === null || validObjectiveCancellation(r.cancellation, institute, r.id);
}
export const matchesObjective = (r: Objective, t: ObjectiveTerms, actor: string) => r.actor_id === actor
  && r.employee_id === t.employee_id && r.title === t.title && r.metric === t.metric && r.currency === t.currency
  && objectiveCents(r.target) === objectiveCents(t.target) && r.first_day === t.first_day && r.last_day === t.last_day
  && r.reason === t.reason && r.idempotency_key === t.idempotency_key;
export function validObjectivePage(value: unknown, institute: string, employee: string, offset: number): value is ObjectivePage {
  const r = value as ObjectivePage, now = certificationInstant(r?.generated_at);
  if (!r || r.institute_id !== institute || r.employee_id !== employee || now === undefined || !r.page || r.page.offset !== offset
    || r.page.limit !== 20 || !count(r.page.total) || !Array.isArray(r.rows)
    || r.rows.length !== Math.min(20, Math.max(0, r.page.total-offset)) || new Set(r.rows.map(v => v?.objective?.id)).size !== r.rows.length) return false;
  return r.rows.every(p => {
    if (!p || !validObjective(p.objective, institute, employee)) return false;
    const o = p.objective, state = o.cancellation ? "cancelled" : now < certificationInstant(o.period_start)! ? "upcoming"
      : now >= certificationInstant(o.period_end)! ? "ended" : "active";
    if (p.period_state !== state) return false;
    if (state === "cancelled") return [p.known_value, p.value, p.achieved, p.source_count, p.missing_amount_sources,
      p.unknown_currency_sources, p.other_currency_sources].every(v => v === null);
    if (!count(p.source_count) || !count(p.missing_amount_sources) || !count(p.unknown_currency_sources) || !count(p.other_currency_sources)
      || p.missing_amount_sources+p.unknown_currency_sources+p.other_currency_sources > p.source_count) return false;
    const known = revenueCents(p.known_value), progress = revenueCents(p.value);
    if (known === undefined) return false;
    if (p.source_count-p.missing_amount_sources-p.unknown_currency_sources-p.other_currency_sources === 0 && known !== 0n) return false;
    if (o.metric === "completed_sessions" && (known !== BigInt(p.source_count)*100n
      || p.missing_amount_sources || p.unknown_currency_sources || p.other_currency_sources)) return false;
    if (state === "upcoming" && (p.source_count !== 0 || known !== 0n)) return false;
    return p.missing_amount_sources || p.unknown_currency_sources ? p.value === null && p.achieved === null
      : progress === known && p.achieved === (known >= objectiveCents(o.target)!);
  });
}
