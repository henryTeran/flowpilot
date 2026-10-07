import { certificationInstant as instant, certificationDate } from "./certification-utils";
import { validCommissionRule, sameCommissionRuleOriginal, validCommissionCalculation, type CommissionRule, type CommissionCalculation } from "./commission-utils";

export type CommissionSourceOption = { line_id: string; ticket_id: string; ticket_number: string; service_id: string; category: string; quantity: number | null;
  amount: string | null; currency: string | null; arrival_at: string | null; paid_at: string; already_attributed: boolean;
  cancellation_clock_future: boolean; exclusion: "rule_cancelled" | "future_rule" | "already_attributed" | "future_cancellation" | "future_closing" | "currency_mismatch" | "outside_period" | "invalid_source" | null;
  calculation: CommissionCalculation | null };
export type CommissionSourceOptions = { institute_id: string; employee_id: string; rule: CommissionRule; day: string; timezone: string;
  start: string; end: string; generated_at: string; basis: "source_closed_day"; complete_sources: false;
  page: { offset: number; limit: number; total: number }; rows: CommissionSourceOption[] };
const text = (v: unknown): v is string => typeof v === "string" && !!v && v.trim() === v && v.length <= 80;
const decimal = (v: unknown): v is string => typeof v === "string" && v.length <= 80 && /^[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?$/.test(v);
// Decimal JSON stays text: no Number conversion or floating-point rounding.
export function commissionSourceMinor(v: unknown): bigint | undefined {
  if (!decimal(v)) return undefined;
  const [mantissa, exponent = "0"] = v.replace(/^[+-]/, "").split(/[eE]/);
  const [whole, fraction = ""] = mantissa.split("."), coefficient = BigInt(whole+fraction);
  if (coefficient === 0n) return 0n;
  if (v.startsWith("-")) return undefined;
  const shift = Number(exponent)-fraction.length+2;
  if (!Number.isSafeInteger(shift) || Math.abs(shift) > 80) return undefined;
  if (shift < 0 && coefficient%10n**BigInt(-shift) !== 0n) return undefined;
  const result = shift >= 0 ? coefficient*10n**BigInt(shift) : coefficient/10n**BigInt(-shift);
  return result <= 9999999999n ? result : undefined;
}
export function validCommissionSourceOptions(v: unknown, institute: string, selected: CommissionRule, day: string,
  start: string, end: string, zone: string, offset: number): v is CommissionSourceOptions {
  const r = v as CommissionSourceOptions, now = instant(r?.generated_at), from = instant(start), until = instant(end);
  if (!r || r.institute_id !== institute || r.employee_id !== selected.employee_id || !validCommissionRule(selected, institute)
    || !validCommissionRule(r.rule, institute, selected.employee_id) || !sameCommissionRuleOriginal(r.rule, selected)
    || r.day !== day || !certificationDate(day) || r.timezone !== zone || from === undefined || until === undefined || until < from
    || instant(r.start) !== from || instant(r.end) !== until || now === undefined || r.basis !== "source_closed_day" || r.complete_sources !== false
    || !Number.isSafeInteger(offset) || offset < 0 || offset%20 !== 0 || !r.page || r.page.offset !== offset || r.page.limit !== 20
    || !Number.isSafeInteger(r.page.total) || r.page.total < 0 || !Array.isArray(r.rows)
    || r.rows.length !== Math.min(20, Math.max(0, r.page.total-offset))) return false;
  const ids = new Set<string>();
  for (const row of r.rows) {
    if (!row || !text(row.line_id) || ids.has(row.line_id) || !text(row.ticket_id) || !text(row.ticket_number) || row.ticket_number.length > 40 || !text(row.service_id) || row.category !== r.rule.category
      || r.rule.service_id !== null && row.service_id !== r.rule.service_id || typeof row.already_attributed !== "boolean"
      || typeof row.cancellation_clock_future !== "boolean" || row.quantity !== null && !Number.isSafeInteger(row.quantity)
      || row.amount !== null && !decimal(row.amount)
      || row.currency !== null && typeof row.currency !== "string" || row.arrival_at !== null && instant(row.arrival_at) === undefined) return false;
    ids.add(row.line_id);
    const paid = instant(row.paid_at), arrival = instant(row.arrival_at), gross = commissionSourceMinor(row.amount);
    if (paid === undefined || paid < from || paid >= until) return false;
    const invalid = gross === undefined || row.quantity === null || row.quantity < 1 || row.quantity > 2147483647
      || arrival === undefined || arrival > paid;
    const expected = r.rule.cancellation ? "rule_cancelled" : instant(r.rule.created_at)! > now ? "future_rule"
      : row.already_attributed ? "already_attributed" : row.cancellation_clock_future ? "future_cancellation" : paid > now ? "future_closing"
      : row.currency !== r.rule.currency ? "currency_mismatch" : paid < instant(r.rule.period_start)! || paid >= instant(r.rule.period_end)! ? "outside_period"
      : invalid ? "invalid_source" : null;
    if (row.exclusion !== expected) return false;
    if (expected !== null) { if (row.calculation !== null) return false; continue; }
    if (!validCommissionCalculation(row.calculation, r.rule, institute)) return false;
    const s = row.calculation.source;
    if (s.line_id !== row.line_id || s.ticket_id !== row.ticket_id || s.service_id !== row.service_id || s.category !== row.category
      || s.currency !== row.currency || s.quantity !== row.quantity || BigInt(s.gross_minor) !== gross || instant(s.arrival_at) !== arrival
      || instant(s.paid_at) !== paid || instant(s.captured_at) !== now) return false;
  }
  return true;
}
