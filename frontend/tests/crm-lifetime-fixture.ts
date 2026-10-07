import type { LifetimeRead } from "../src/crm-lifetime-utils";
import { crmProfile } from "./crm-fixture";
const start = "2026-10-06T00:00:00Z";
export function crmLifetime(): LifetimeRead {
  const p = crmProfile(), billing = p.segment!.billing;
  billing.closed_tickets = 1; billing.frequency_per_microsecond.numerator = "1";
  billing.last_recorded_closed_at = "2026-10-06T23:59:59.999999Z"; billing.recorded_recency_us = "1";
  billing.currencies = [{ currency: "CHF",closed_tickets: 1,known_amount_tickets: 1,missing_amount_tickets: 0,invalid_amount_tickets: 0,
    known_gross_minor: "101",recorded_average_basket_minor: { numerator: "101",denominator: "1" } }];
  const assumptions = { institute_id: "i",customer_id: "customer_a",model: "constant_observed_rate_finite_remaining_lifetime_undiscounted_v1" as const,
    currency: "CHF" as const,expected_active_us: "172800000000",activity_fraction: { numerator: "1",denominator: "2" },
    gross_contribution_margin: { numerator: "1",denominator: "3" },future_relationship_cost_minor: "100" };
  return { window: { ...billing.window }, customer: p.customer,
    original: { id: "original",institute_id: "i",customer_id: "customer_a",actor_id: "manager",created_at: start,
      assumptions,previous_id: null,reason: "Explicit terms",idempotency_key: "key" },unavailable_reason: null,
    scenario: { basis: "declared_remaining_lifetime_scenario",assumptions: structuredClone(assumptions),billing,
      undated_paid_tickets: 0,future_paid_tickets: 0,assumed_active_until: "2026-10-09T00:00:00Z",
      projected_gross_minor: { numerator: "101",denominator: "1" },projected_contribution_minor: { numerator: "101",denominator: "3" },
      remaining_clv_minor: { numerator: "-199",denominator: "3" },unavailable_reason: null,
      complete_customer_history: false,validated_prediction: false,discounted: false } };
}
