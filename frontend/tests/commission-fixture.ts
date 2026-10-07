import { commissionStates, type CommissionRule, type Commission, type CommissionDay } from "../src/commission-utils";
export const props = { institute: "inst", employee: "emp", day: "2026-10-25", start: "2026-10-24T22:00:00Z", end: "2026-10-25T23:00:00Z", timezone: "Europe/Zurich" };
export function rule(): CommissionRule {
  return { id: "rule", institute_id: "inst", employee_id: "emp", title: "Explicit policy", basis: "closed_attributed_line_gross", currency: "CHF",
    category: "care", service_id: null, rate_basis_points: 1000, rounding: "half_up", first_day: props.day, last_day: props.day,
    timezone: props.timezone, period_start: props.start, period_end: props.end, actor_id: "manager", reason: "Explicit rule", idempotency_key: "rule-key",
    created_at: "2026-10-25T10:00:00Z", cancellation: null };
}
export function original(): Commission {
  const r = rule();
  return { id: "commission", institute_id: "inst", employee_id: "emp", ticket_id: "ticket", rule_id: r.id, line_id: "line",
    actor_id: "manager", reason: "Explicit credit", idempotency_key: "commission-key", created_at: "2026-10-25T12:00:00.000001Z", cancellation: null,
    rule_capture: r, calculation: { terms: { employee_id: r.employee_id, basis: r.basis, currency: r.currency, category: r.category,
      service_id: r.service_id, rate_basis_points: r.rate_basis_points, rounding: r.rounding, period_start: r.period_start, period_end: r.period_end },
    source: { institute_id: "inst", employee_id: "emp", ticket_id: "ticket", line_id: "line", service_id: "service", category: "care", currency: "CHF",
      quantity: 3, gross_minor: "1035", arrival_at: "2026-10-25T09:00:00Z", paid_at: "2026-10-25T11:00:00Z", captured_at: "2026-10-25T12:00:00.000001Z" },
    unrounded_numerator: "1035000", rounding_remainder: 5000, amount_minor: "104" } };
}
export function snapshot(): CommissionDay {
  const counts = Object.fromEntries(commissionStates.map(k => [k, k === "recorded" ? 1 : 0])) as CommissionDay["counts"];
  return { institute_id: props.institute, employee_id: props.employee, day: props.day, timezone: props.timezone, start: props.start, end: props.end,
    generated_at: "2026-10-25T12:00:00.000002Z", basis: "commission_recorded_at", complete_entitlement: false, payable_total: null,
    page: { offset: 0, limit: 20, total: 1 }, counts, currencies: [{ currency: "CHF", counts: { ...counts },
      amounts_minor: Object.fromEntries(commissionStates.map(k => [k, k === "recorded" ? "104" : "0"])) as CommissionDay["currencies"][number]["amounts_minor"] }],
    rows: [{ original: original(), state: "recorded" }] };
}
