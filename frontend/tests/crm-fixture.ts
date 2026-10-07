import type { SegmentProfile } from "../src/crm-segment-utils";
import type { ReturnRead } from "../src/crm-return-utils";
export function crmEmptyReturn(): ReturnRead {
  return { complete_execution_coverage: false, complete_service_coverage: false,
    summary: { window: { institute_id: "i", customer_id: "customer_a", start: "2026-10-06T00:00:00Z", end: "2026-10-07T00:00:00Z", captured_at: "2026-10-07T00:00:00Z" },
      basis: "recorded_completed_ticket_care", execution_count: 0, episode_count: 0, known_gap_count: 0, overlapping_gap_count: 0,
      known_gap_total_us: "0", average_return_gap_us: null, complete_customer_history: false, inferred_booking_credit: false },
    diagnostics: { unlinked_ticket: 0, invalid_owner_or_service: 0, invalid_actual_times: 0 },
    page: { offset: 0, limit: 20, total: 0 }, episodes: [], gaps: [] };
}
export function crmProfile(): SegmentProfile {
  const customer = { institute_id: "i", customer_id: "customer_a", created_at: "2026-10-06T23:59:59.999950Z" };
  const policy = { institute_id: "i", observation_us: 86400000000, new_customer_us: 100,
    at_risk_us: 1000, dormant_us: 2000, loyal_min_tickets: 2, vip_min_tickets: 3, vip_currency: "CHF" as const, vip_gross_minor: "300" };
  return { institute_id: "i", customer_id: "customer_a", captured_at: "2026-10-07T00:00:00Z", customer,
    policy_original: { id: "p", institute_id: "i", actor_id: "manager", created_at: "2026-10-06T00:00:00Z", policy,
      reason: "Explicit policy", idempotency_key: "key", previous_policy_id: null },
    undated_paid_tickets: 0, future_paid_tickets: 0, unavailable_reason: null, complete_customer_history: false,
    segment: { basis: "declared_policy_observed_billing", policy, customer, undated_paid_tickets: 0,
      state: "NEW", reason: "recent_registration", complete_customer_history: false,
      billing: { window: { institute_id: "i", customer_id: "customer_a", start: "2026-10-06T00:00:00Z",
        end: "2026-10-07T00:00:00Z", captured_at: "2026-10-07T00:00:00Z" }, basis: "retained_closed_tickets",
        closed_tickets: 0, frequency_per_microsecond: { numerator: "0", denominator: "86400000000" },
        last_recorded_closed_at: null, recorded_recency_us: null, unknown_currency_tickets: 0, currencies: [],
        complete_customer_history: false, complete_currency_classification: true, predicted_clv: null } } };
}
