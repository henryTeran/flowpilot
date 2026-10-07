import { type Occupation } from "../src/occupation-utils";
export const props = { institute: "inst", employee: "emp", day: "2025-10-26", start: "2025-10-25T22:00:00Z", end: "2025-10-26T23:00:00Z", timezone: "Europe/Zurich" };
export function snapshot(): Occupation {
  return { work_hours: { institute_id: "inst", employee_id: "emp", day: props.day, timezone: props.timezone, start: props.start, end: props.end,
    generated_at: "2026-10-07T12:00:00Z", page: { offset: 0, limit: 20, total: 1 }, active_sources: 1, future_end_sources: 0, overlap_sources: 0,
    known_declared_duration_us: "7200000000", known_union_duration_us: "7200000000", recorded_duration_us: "7200000000", complete_attendance: false,
    rows: [{ interval: { id: "work", institute_id: "inst", employee_id: "emp", actor_id: "manager", reason: "Declared", idempotency_key: "work-key",
      created_at: "2026-10-07T12:00:00Z", start_time: "2025-10-26T03:00:00Z", end_time: "2025-10-26T05:00:00Z", cancellation: null },
      clipped_start: "2025-10-26T03:00:00Z", clipped_end: "2025-10-26T05:00:00Z", duration_us: "7200000000", exclusion: null }] },
    page: { offset: 0, limit: 20, total: 2 }, diagnostics: { retained: 2, missing_start: 0, missing_end: 0, invalid_interval: 0, future_end: 0, unfinalized: 0 },
    known_busy_duration_us: "7200000001", covered_busy_duration_us: "3600000001", outside_recorded_work_duration_us: "3600000000",
    recorded_occupation_basis_points: "5000", complete_activity: false,
    rows: [{ kind: "session", id: "session", service_id: "care", status: "completed", actual_start: "2025-10-26T02:00:00Z", actual_end: "2025-10-26T04:00:00Z",
      clipped_start: "2025-10-26T02:00:00Z", clipped_end: "2025-10-26T04:00:00Z", duration_us: "7200000000", exclusion: null },
    { kind: "appointment", id: "appointment", service_id: "care", status: "completed", actual_start: "2025-10-26T03:30:00Z", actual_end: "2025-10-26T04:00:00.000001Z",
      clipped_start: "2025-10-26T03:30:00Z", clipped_end: "2025-10-26T04:00:00.000001Z", duration_us: "1800000001", exclusion: null }] };
}
