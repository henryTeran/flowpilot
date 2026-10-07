import { certificationInstant } from "./certification-utils";

type Currency = "CHF" | "EUR" | null;
type Ratio = { numerator: string; denominator: string };
export type RevenueAmounts = { currency: Currency; source_count: number; known_amount_count: number; missing_amount_count: number; invalid_amount_count: number; known_gross_minor: string; complete_gross_minor: string | null; average_minor: Ratio | null };
export type RevenueBilling = {
  window: { institute_id: string; start: string; end: string; captured_at: string };
  basis: "recorded_paid_tickets_and_active_invoice_lines"; ticket_count: number; ticket_amounts: RevenueAmounts[];
  active_line_count: number; service_mix: { service_id: string; category: "care" | "retail" | null; currency: Currency; line_count: number; units: string; amounts: RevenueAmounts }[];
  tickets_without_active_lines: number; tickets_with_unknown_category: number; care_tickets: number; care_and_retail_tickets: number;
  recorded_retail_attach_ratio: Ratio | null; institute_undated_paid_tickets: number;
  complete_sales_history: false; settlement_confirmed: false; projected_revenue: null;
};
const keys = (v: unknown, names: string): v is Record<string, unknown> => !!v && typeof v === "object" && !Array.isArray(v)
  && Object.keys(v).sort().join(" ") === names.split(" ").sort().join(" ");
const count = (v: unknown): v is number => typeof v === "number" && Number.isSafeInteger(v) && v >= 0;
const unsigned = (v: unknown): v is string => typeof v === "string" && /^(0|[1-9][0-9]*)$/.test(v) && v.length <= 40;
const currency = (v: unknown): v is Currency => v === null || v === "CHF" || v === "EUR";
const id = (v: unknown): v is string => typeof v === "string" && v.length > 0 && v.length <= 80 && v.trim() === v;
function ratio(v: unknown, numerator: string, denominator: string) {
  return keys(v, "numerator denominator") && v.numerator === numerator && v.denominator === denominator;
}
function amounts(v: unknown): v is RevenueAmounts {
  if (!keys(v, "currency source_count known_amount_count missing_amount_count invalid_amount_count known_gross_minor complete_gross_minor average_minor")
    || !currency(v.currency) || !count(v.source_count) || !v.source_count || !count(v.known_amount_count)
    || !count(v.missing_amount_count) || !count(v.invalid_amount_count) || !unsigned(v.known_gross_minor)) return false;
  if (BigInt(v.known_amount_count) + BigInt(v.missing_amount_count) + BigInt(v.invalid_amount_count) !== BigInt(v.source_count)
    || BigInt(v.known_gross_minor) > BigInt(v.known_amount_count) * 9999999999n) return false;
  const complete = v.currency !== null && v.known_amount_count === v.source_count;
  return v.complete_gross_minor === (complete ? v.known_gross_minor : null)
    && (complete ? ratio(v.average_minor, v.known_gross_minor, String(v.source_count)) : v.average_minor === null);
}
export function validRevenueBilling(v: unknown, institute: string, period: { start: string; end: string }): v is RevenueBilling {
  if (!keys(v, "window basis ticket_count ticket_amounts active_line_count service_mix tickets_without_active_lines tickets_with_unknown_category care_tickets care_and_retail_tickets recorded_retail_attach_ratio institute_undated_paid_tickets complete_sales_history settlement_confirmed projected_revenue")
    || !keys(v.window, "institute_id start end captured_at") || v.window.institute_id !== institute
    || v.basis !== "recorded_paid_tickets_and_active_invoice_lines" || v.complete_sales_history !== false
    || v.settlement_confirmed !== false || v.projected_revenue !== null) return false;
  const start = certificationInstant(v.window.start), end = certificationInstant(v.window.end), capture = certificationInstant(v.window.captured_at);
  if (start === undefined || end === undefined || capture === undefined || start >= end || end > capture
    || start !== certificationInstant(period.start) || end !== certificationInstant(period.end)) return false;
  const counts = [v.ticket_count, v.active_line_count, v.tickets_without_active_lines, v.tickets_with_unknown_category,
    v.care_tickets, v.care_and_retail_tickets, v.institute_undated_paid_tickets];
  if (!counts.every(count) || !Array.isArray(v.ticket_amounts) || !v.ticket_amounts.every(amounts)
    || !Array.isArray(v.service_mix)) return false;
  const total = v.ticket_count as number, care = v.care_tickets as number, attached = v.care_and_retail_tickets as number;
  if (attached > care || care > total || (v.tickets_without_active_lines as number) > total || (v.tickets_with_unknown_category as number) > total) return false;
  if (new Set(v.ticket_amounts.map(g => g.currency)).size !== v.ticket_amounts.length
    || v.ticket_amounts.reduce((n, g) => n + BigInt(g.source_count), 0n) !== BigInt(total)) return false;
  const seen = new Set<string>(); let lines = 0n;
  for (const g of v.service_mix) {
    if (!keys(g, "service_id category currency line_count units amounts") || !id(g.service_id)
      || ![null, "care", "retail"].includes(g.category as string | null) || !currency(g.currency)
      || !count(g.line_count) || !unsigned(g.units) || !amounts(g.amounts)
      || g.currency !== g.amounts.currency || g.line_count !== g.amounts.source_count || BigInt(g.units) < BigInt(g.line_count)) return false;
    const key = JSON.stringify([g.service_id, g.category, g.currency]);
    if (seen.has(key)) return false; seen.add(key); lines += BigInt(g.line_count);
  }
  if (lines !== BigInt(v.active_line_count as number)) return false;
  return care > 0 && v.tickets_without_active_lines === 0 && v.tickets_with_unknown_category === 0
    ? ratio(v.recorded_retail_attach_ratio, String(attached), String(care)) : v.recorded_retail_attach_ratio === null;
}
export function revenueMoney(minor: string): string {
  const n = BigInt(minor); return `${n / 100n}.${String(n % 100n).padStart(2, "0")}`;
}
export function revenueAverage(value: Ratio): string {
  const n = BigInt(value.numerator), d = BigInt(value.denominator);
  return `${n % d ? "≈ " : ""}${revenueMoney(String((2n * n + d) / (2n * d)))}`;
}
