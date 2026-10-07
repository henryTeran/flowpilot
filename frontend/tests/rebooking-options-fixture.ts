import { original, props } from "./rebooking-fixture";
import type { SourceChoices, TargetChoices } from "../src/rebooking-options";
export function sources(): SourceChoices {
  const o = original(), s = o.source_capture;
  return { institute_id: "inst", employee_id: "emp", day: props.day, timezone: props.timezone, start: props.start, end: props.end,
    generated_at: o.created_at, basis: "actual_completion_day", complete_sources: false, page: { offset: 0, limit: 20, total: 1 },
    rows: [{ kind: s.kind, id: s.id, service_id: s.service_id, actual_start: s.actual_start, actual_end: s.actual_end, customer_id: s.customer_id,
      customer_known: true, already_attributed: false, exclusion: null, capture: s }] };
}
export function targets(): TargetChoices {
  const o = original(), b = o.booking_capture;
  return { institute_id: "inst", generated_at: o.created_at, source: o.source_capture, page: { offset: 0, limit: 20, total: 1 },
    rows: [{ id: b.appointment_id, employee_id: "other-performer", service_id: "care", status: "scheduled", customer_id: o.source_capture.customer_id,
      booked_start: b.current_start, booked_end: b.current_end, creation_events: 1, already_attributed: false, exclusion: null, capture: b }] };
}
