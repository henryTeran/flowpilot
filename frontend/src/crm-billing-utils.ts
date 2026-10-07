import { certificationInstant as instant } from "./certification-utils";

export type BillingRatio = { numerator: string; denominator: string };
export type BillingWindow = { institute_id: string; customer_id: string; start: string; end: string; captured_at: string };
export type BillingCurrency = { currency: "CHF" | "EUR"; closed_tickets: number; known_amount_tickets: number;
  missing_amount_tickets: number; invalid_amount_tickets: number; known_gross_minor: string;
  recorded_average_basket_minor: BillingRatio | null };
export type RecordedBilling = { window: BillingWindow; basis: "retained_closed_tickets"; closed_tickets: number;
  frequency_per_microsecond: BillingRatio; last_recorded_closed_at: string | null; recorded_recency_us: string | null;
  unknown_currency_tickets: number; currencies: BillingCurrency[]; complete_customer_history: false;
  complete_currency_classification: boolean; predicted_clv: null };

const count = (v: unknown): v is number => Number.isSafeInteger(v) && (v as number) >= 0;
export function crmUnsigned(v: unknown): bigint | undefined {
  if (typeof v === "string" && v.length <= 30 && /^(0|[1-9]\d*)$/.test(v)) return BigInt(v);
}
function ratio(v: unknown, numerator: bigint, denominator: bigint): v is BillingRatio {
  const r = v as BillingRatio;
  return !!r && denominator > 0n && crmUnsigned(r.numerator) === numerator
    && crmUnsigned(r.denominator) === denominator;
}

export function validRecordedBilling(value: unknown, institute: string, customer: string,
  expected?: { start: string; end: string; captured_at?: string }): value is RecordedBilling {
  const r = value as RecordedBilling;
  if (!r || !r.window || r.window.institute_id !== institute || r.window.customer_id !== customer
    || r.basis !== "retained_closed_tickets" || !count(r.closed_tickets) || !count(r.unknown_currency_tickets)
    || !Array.isArray(r.currencies) || r.currencies.length > 2 || r.complete_customer_history !== false
    || r.predicted_clv !== null || r.complete_currency_classification !== (r.unknown_currency_tickets === 0)) return false;
  const start = instant(r.window.start), end = instant(r.window.end), captured = instant(r.window.captured_at);
  if (start === undefined || end === undefined || captured === undefined || start >= end || end > captured
    || !ratio(r.frequency_per_microsecond, BigInt(r.closed_tickets), end-start)) return false;
  if (expected && (instant(expected.start) !== start || instant(expected.end) !== end
    || expected.captured_at !== undefined && instant(expected.captured_at) !== captured)) return false;
  if (r.closed_tickets === 0) {
    if (r.last_recorded_closed_at !== null || r.recorded_recency_us !== null) return false;
  } else {
    const last = instant(r.last_recorded_closed_at);
    if (last === undefined || last < start || last >= end || crmUnsigned(r.recorded_recency_us) !== captured-last) return false;
  }
  let total = BigInt(r.unknown_currency_tickets);
  let previous = "";
  for (const g of r.currencies) {
    if (!g || !["CHF", "EUR"].includes(g.currency) || g.currency <= previous || !count(g.closed_tickets)
      || g.closed_tickets === 0 || !count(g.known_amount_tickets) || !count(g.missing_amount_tickets)
      || !count(g.invalid_amount_tickets)) return false;
    previous = g.currency;
    const known = BigInt(g.known_amount_tickets), missing = BigInt(g.missing_amount_tickets), invalid = BigInt(g.invalid_amount_tickets);
    if (known+missing+invalid !== BigInt(g.closed_tickets)) return false;
    const gross = crmUnsigned(g.known_gross_minor);
    if (gross === undefined || gross > known*9999999999n) return false;
    if (missing+invalid === 0n) {
      if (!ratio(g.recorded_average_basket_minor, gross, BigInt(g.closed_tickets))) return false;
    } else if (g.recorded_average_basket_minor !== null) return false;
    total += BigInt(g.closed_tickets);
  }
  return total === BigInt(r.closed_tickets);
}
