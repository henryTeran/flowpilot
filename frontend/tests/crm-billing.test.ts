import test from "node:test";
import assert from "node:assert/strict";
import { validRecordedBilling, type RecordedBilling } from "../src/crm-billing-utils";

function sample(): RecordedBilling {
  return { window: { institute_id: "i", customer_id: "customer_a", start: "2026-10-06T00:00:00Z",
    end: "2026-10-07T00:00:00Z", captured_at: "2026-10-07T00:00:00.000001Z" },
    basis: "retained_closed_tickets", closed_tickets: 3,
    frequency_per_microsecond: { numerator: "3", denominator: "86400000000" },
    last_recorded_closed_at: "2026-10-06T23:59:59.999999Z", recorded_recency_us: "2", unknown_currency_tickets: 0,
    currencies: [{ currency: "CHF", closed_tickets: 2, known_amount_tickets: 2, missing_amount_tickets: 0,
      invalid_amount_tickets: 0, known_gross_minor: "201", recorded_average_basket_minor: { numerator: "201", denominator: "2" } },
    { currency: "EUR", closed_tickets: 1, known_amount_tickets: 0, missing_amount_tickets: 1,
      invalid_amount_tickets: 0, known_gross_minor: "0", recorded_average_basket_minor: null }],
    complete_customer_history: false, complete_currency_classification: true, predicted_clv: null };
}
const valid = (v: unknown) => validRecordedBilling(v, "i", "customer_a");

test("recorded billing validates exact ratios, scope and microsecond chronology", () => {
  const r = sample(); assert.equal(valid(r), true);
  assert.equal(validRecordedBilling(r, "other", "customer_a"), false);
  assert.equal(validRecordedBilling(r, "i", "other"), false);
  assert.equal(validRecordedBilling(r, "i", "customer_a", { start: "2026-10-06T02:00:00+02:00", end: r.window.end }), true);
  assert.equal(validRecordedBilling(r, "i", "customer_a", { start: r.window.start, end: r.window.end, captured_at: r.window.end }), false);
  for (const change of [
    (v: RecordedBilling) => { v.recorded_recency_us = "1"; },
    (v: RecordedBilling) => { v.last_recorded_closed_at = v.window.end; },
    (v: RecordedBilling) => { v.window.start = "2026-10-06"; },
    (v: RecordedBilling) => { v.frequency_per_microsecond.denominator = "86400000001"; },
    (v: RecordedBilling) => { v.frequency_per_microsecond.numerator = "4"; },
    (v: RecordedBilling) => { v.currencies[0].recorded_average_basket_minor!.numerator = "200"; },
    (v: RecordedBilling) => { v.currencies[1].recorded_average_basket_minor = { numerator: "0", denominator: "1" }; },
    (v: RecordedBilling) => { v.currencies[0].known_gross_minor = "20000000000"; },
    (v: RecordedBilling) => { v.currencies[0].missing_amount_tickets = 1; },
    (v: RecordedBilling) => { v.currencies.reverse(); },
    (v: RecordedBilling) => { v.currencies.push(v.currencies[0]); },
  ]) { const value = sample(); change(value); assert.equal(valid(value), false); }
  for (const value of [null, {}, { ...r, closed_tickets: true }, { ...r, closed_tickets: "3" },
    { ...r, complete_customer_history: true }, { ...r, predicted_clv: "201" },
    { ...r, unknown_currency_tickets: 1 }, { ...r, currencies: [null] },
    { ...r, frequency_per_microsecond: { numerator: "3", denominator: 86400000000 } },
    { ...r, closed_tickets: Number.MAX_SAFE_INTEGER+1 }]) assert.equal(valid(value), false);
});

test("empty and unknown cohorts preserve diagnostics without fabricating baskets", () => {
  const r = sample(); r.closed_tickets = 0; r.frequency_per_microsecond.numerator = "0";
  r.last_recorded_closed_at = null; r.recorded_recency_us = null; r.currencies = [];
  assert.equal(valid(r), true);
  r.recorded_recency_us = "0"; assert.equal(valid(r), false);
  const unknown = sample(); unknown.unknown_currency_tickets = 1; unknown.closed_tickets = 4;
  unknown.frequency_per_microsecond.numerator = "4"; unknown.complete_currency_classification = false;
  assert.equal(valid(unknown), true);
  const invalid = sample(); invalid.currencies[1].missing_amount_tickets = 0;
  invalid.currencies[1].invalid_amount_tickets = 1; assert.equal(valid(invalid), true);
});

test("gross aggregates beyond safe numeric range remain exact canonical strings", () => {
  const r = sample(); r.closed_tickets = 1000000; r.frequency_per_microsecond.numerator = "1000000";
  r.currencies = [{ currency: "CHF", closed_tickets: 1000000, known_amount_tickets: 1000000,
    missing_amount_tickets: 0, invalid_amount_tickets: 0, known_gross_minor: "9999999999000000",
    recorded_average_basket_minor: { numerator: "9999999999000000", denominator: "1000000" } }];
  assert.equal(valid(r), true);
  for (const gross of ["01", "-1", "1.5", "1e2", "NaN", "9999999999000001"]) {
    const value = structuredClone(r); value.currencies[0].known_gross_minor = gross; assert.equal(valid(value), false);
  }
});

test("long-horizon exact denominators do not pass through numeric JSON", () => {
  const r = sample(); r.window.start = "0001-01-01T00:00:00Z";
  const duration = (BigInt(Date.parse(r.window.end))-BigInt(Date.parse(r.window.start)))*1000n;
  assert.ok(duration > BigInt(Number.MAX_SAFE_INTEGER));
  r.frequency_per_microsecond.denominator = duration.toString();
  assert.equal(valid(r), true);
  r.frequency_per_microsecond.denominator = (duration+1n).toString();
  assert.equal(valid(r), false);
});
