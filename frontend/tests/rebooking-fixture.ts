import { rebookingStates, type Rebooking, type RebookingDay } from "../src/rebooking-utils";
export const props = { institute: "inst", employee: "emp", day: "2026-10-07", start: "2026-10-06T22:00:00Z", end: "2026-10-07T22:00:00Z", timezone: "Europe/Zurich" };
export function original(): Rebooking {
  return { id: "original", institute_id: "inst", employee_id: "emp", source_kind: "session", source_id: "session", target_appointment_id: "target",
    reason: "Declared", idempotency_key: "original-key", actor_id: "manager", created_at: "2026-10-07T12:00:00Z", cancellation: null,
    source_capture: { kind: "session", id: "session", employee_id: "emp", service_id: "care", customer_id: "customer",
      actual_start: "2026-10-07T10:00:00Z", actual_end: "2026-10-07T11:00:00Z" },
    booking_capture: { appointment_id: "target", creation_event_id: "event", created_at: "2026-10-07T11:00:00.000001Z",
      original_start: "2026-10-08T12:00:00Z", original_end: "2026-10-08T13:00:00Z", current_start: "2026-10-08T12:00:00Z", current_end: "2026-10-08T13:00:00Z" } };
}
export function snapshot(): RebookingDay {
  return { institute_id: "inst", employee_id: "emp", day: props.day, timezone: props.timezone, start: props.start, end: props.end, generated_at: "2026-10-07T12:00:00Z",
    basis: "declaration_recorded_at", page: { offset: 0, limit: 20, total: 1 }, counts: { ...Object.fromEntries(rebookingStates.map(k => [k, 0])), booked_return: 1 } as RebookingDay["counts"],
    complete_attribution: false, conversion_basis_points: null,
    rows: [{ original: original(), target_status: "scheduled", target_customer_id: "customer", actual_start: null, actual_end: null, state: "booked_return" }] };
}
