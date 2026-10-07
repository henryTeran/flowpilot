import { certificationInstant } from "./certification-utils";
type Currency = "CHF" | "EUR" | null;
export type RevenueLine = { id: string; ticket_id: string; ticket_number: string; service_id: string; employee_id: string;
  paid_at: string; currency: Currency; category: string; quantity: number; amount: string | null };
export type RevenueGroup = { currency: Currency; line_count: number; ticket_count: number; amount_known_total: string | null;
  amount_missing_lines: number; total: string | null };
export type EmployeeRevenue = { institute_id: string; employee_id: string; day: string; start: string; end: string;
  generated_at: string; page: { offset: number; limit: number; total: number }; rows: RevenueLine[];
  currencies: RevenueGroup[]; institute_unattributed_lines: number };
const count = (value: unknown): value is number => Number.isSafeInteger(value) && (value as number) >= 0;
const text = (value: unknown): value is string => typeof value === "string" && value === value.trim() && !!value;
const currency = (value: unknown): value is Currency => value === null || value === "CHF" || value === "EUR";
export function revenueCents(value: unknown): bigint | undefined {
  if (typeof value !== "string" || !/^-?\d+(?:\.\d{1,2})?$/.test(value)) return;
  const sign = value.startsWith("-") ? -1n : 1n, [whole, fraction = ""] = value.replace(/^-/, "").split(".");
  return sign*(BigInt(whole)*100n+BigInt(fraction.padEnd(2, "0")));
}
export function validEmployeeRevenue(value: unknown, institute: string, employee: string, day: string,
  start: string, end: string, offset: number): value is EmployeeRevenue {
  const row = value as EmployeeRevenue, from = certificationInstant(start), until = certificationInstant(end);
  if (!row || row.institute_id !== institute || row.employee_id !== employee || row.day !== day || from === undefined || until === undefined
    || until < from || certificationInstant(row.start) !== from || certificationInstant(row.end) !== until || certificationInstant(row.generated_at) === undefined
    || !row.page || row.page.offset !== offset || row.page.limit !== 50 || !count(row.page.total) || !count(row.institute_unattributed_lines)
    || !Array.isArray(row.rows) || row.rows.length !== Math.min(50, Math.max(0, row.page.total-offset)) || !Array.isArray(row.currencies) || row.currencies.length > 3) return false;
  if (new Set(row.rows.map(item => item?.id)).size !== row.rows.length || new Set(row.currencies.map(item => item?.currency)).size !== row.currencies.length) return false;
  if (!row.currencies.every(group => group && currency(group.currency) && count(group.line_count) && group.line_count > 0
    && count(group.ticket_count) && group.ticket_count > 0 && group.ticket_count <= group.line_count && count(group.amount_missing_lines)
    && group.amount_missing_lines <= group.line_count && (group.currency === null ? group.amount_known_total === null && group.total === null
      : revenueCents(group.amount_known_total) !== undefined && (group.amount_missing_lines ? group.total === null
        : revenueCents(group.total) === revenueCents(group.amount_known_total))))) return false;
  if (row.currencies.reduce((sum, group) => sum+group.line_count, 0) !== row.page.total) return false;
  if (!row.rows.every(line => line && text(line.id) && text(line.ticket_id) && text(line.ticket_number) && text(line.service_id)
    && line.employee_id === employee && text(line.category) && count(line.quantity) && line.quantity > 0 && currency(line.currency)
    && row.currencies.some(group => group.currency === line.currency) && (line.amount === null || revenueCents(line.amount) !== undefined)
    && certificationInstant(line.paid_at) !== undefined && certificationInstant(line.paid_at)! >= from && certificationInstant(line.paid_at)! < until)) return false;
  const tickets = new Map<string, RevenueLine>();
  for (const line of row.rows) {
    const old = tickets.get(line.ticket_id);
    if (old && (old.currency !== line.currency || old.ticket_number !== line.ticket_number || certificationInstant(old.paid_at) !== certificationInstant(line.paid_at))) return false;
    tickets.set(line.ticket_id, line);
  }
  return row.currencies.every(group => {
    const lines = row.rows.filter(line => line.currency === group.currency), missing = lines.filter(line => line.amount === null).length;
    if (lines.length > group.line_count || missing > group.amount_missing_lines || new Set(lines.map(line => line.ticket_id)).size > group.ticket_count) return false;
    return row.page.total > 50 || offset > 0 || (missing === group.amount_missing_lines && new Set(lines.map(line => line.ticket_id)).size === group.ticket_count
      && (group.currency === null || lines.reduce((sum, line) => sum+(revenueCents(line.amount) ?? 0n), 0n) === revenueCents(group.amount_known_total)));
  });
}
