import { original, rule, props } from "./commission-fixture";
import type { CommissionSourceOptions } from "../src/commission-options";
export function options(): CommissionSourceOptions {
  const calculation = original().calculation;
  return { institute_id: "inst", employee_id: "emp", rule: rule(), day: props.day, timezone: props.timezone,
    start: props.start, end: props.end, generated_at: calculation.source.captured_at, basis: "source_closed_day", complete_sources: false,
    page: { offset: 0, limit: 20, total: 1 }, rows: [{ line_id: "line", ticket_id: "ticket", ticket_number: "BM-001", service_id: "service", category: "care",
      quantity: 3, amount: "10.35", currency: "CHF", arrival_at: calculation.source.arrival_at, paid_at: calculation.source.paid_at,
      already_attributed: false, cancellation_clock_future: false, exclusion: null, calculation }] };
}
