import { certificationDate, certificationInstant } from "./certification-utils";
import { instituteMidnight } from "./outlook-utils";
import { validOccupation, type Occupation } from "./occupation-utils";
import { occupationDiagnosticKeys } from "./occupation-math";
import { workDuration } from "./work-hours-utils";
type Ratio = { numerator: string; denominator: string };
export type RevenueCapacity = {
  window: { institute_id: string; start: string; end: string; captured_at: string }; day: string; timezone: string;
  basis: "declared_work_intersected_with_finalized_recorded_activity";
  page: { offset: number; limit: number; total: number };
  rows: { employee_id: string; evidence: Occupation; recorded_unoccupied_duration_us: string | null; recorded_utilization_ratio: Ratio | null }[];
  employee_count: number; employees_without_usable_hours: number; employees_with_uncertain_activity: number;
  known_declared_union_duration_us: string; known_covered_busy_duration_us: string; known_outside_declared_work_duration_us: string;
  recorded_unoccupied_duration_us: string | null; recorded_utilization_ratio: Ratio | null;
  complete_attendance: false; complete_activity: false; physical_unused_capacity: null; bookable_capacity: null; estimated_value: null;
};
const keys = (v: unknown, names: string): v is Record<string, unknown> => !!v && typeof v === "object" && !Array.isArray(v)
  && Object.keys(v).sort().join(" ") === names.split(" ").sort().join(" ");
const count = (v: unknown): v is number => typeof v === "number" && Number.isSafeInteger(v) && v >= 0;
function ratio(v: unknown, n: bigint, d: bigint) {
  return keys(v, "numerator denominator") && v.numerator === String(n) && v.denominator === String(d);
}
export function capacityDayWindow(day: string, timezone: string) {
  if (!certificationDate(day)) return;
  const next = new Date(`${day}T12:00:00Z`); next.setUTCDate(next.getUTCDate() + 1);
  const following = next.toISOString().slice(0, 10);
  if (!certificationDate(following)) return;
  const start = instituteMidnight(day, timezone), end = instituteMidnight(following, timezone);
  const first = certificationInstant(start), last = certificationInstant(end);
  if (!start || !end || first === undefined || last === undefined || last <= first) return;
  return { start, end };
}
export function validRevenueCapacity(v: unknown, institute: string, day: string, timezone: string, offset: number): v is RevenueCapacity {
  const expected = capacityDayWindow(day, timezone);
  if (!expected || !keys(v, "window day timezone basis page rows employee_count employees_without_usable_hours employees_with_uncertain_activity known_declared_union_duration_us known_covered_busy_duration_us known_outside_declared_work_duration_us recorded_unoccupied_duration_us recorded_utilization_ratio complete_attendance complete_activity physical_unused_capacity bookable_capacity estimated_value")
    || !keys(v.window, "institute_id start end captured_at") || v.window.institute_id !== institute || v.day !== day || v.timezone !== timezone
    || v.basis !== "declared_work_intersected_with_finalized_recorded_activity" || v.complete_attendance !== false || v.complete_activity !== false
    || v.physical_unused_capacity !== null || v.bookable_capacity !== null || v.estimated_value !== null) return false;
  const first = certificationInstant(v.window.start), last = certificationInstant(v.window.end), now = certificationInstant(v.window.captured_at);
  if (first !== certificationInstant(expected.start) || last !== certificationInstant(expected.end) || now === undefined || last === undefined || first === undefined || last > now) return false;
  if (!count(v.employee_count) || !count(v.employees_without_usable_hours) || !count(v.employees_with_uncertain_activity)
    || v.employees_without_usable_hours > v.employee_count || v.employees_with_uncertain_activity > v.employee_count
    || !keys(v.page, "offset limit total") || !count(offset) || v.page.offset !== offset || v.page.limit !== 20 || v.page.total !== v.employee_count
    || !Array.isArray(v.rows) || v.rows.length !== Math.min(20, Math.max(0, v.employee_count - offset))) return false;
  const work = workDuration(v.known_declared_union_duration_us), busy = workDuration(v.known_covered_busy_duration_us), outside = workDuration(v.known_outside_declared_work_duration_us);
  if (work === undefined || busy === undefined || outside === undefined || busy > work || work > BigInt(v.employee_count) * (last-first)
    || busy + outside > BigInt(v.employee_count) * (last-first)) return false;
  const usable = v.employee_count > 0 && !v.employees_without_usable_hours && !v.employees_with_uncertain_activity;
  if (v.recorded_unoccupied_duration_us !== (usable ? String(work-busy) : null)
    || (usable && work > 0n ? !ratio(v.recorded_utilization_ratio, busy, work) : v.recorded_utilization_ratio !== null)) return false;
  let rowWork = 0n, rowBusy = 0n, rowOutside = 0n, missing = 0, uncertain = 0, previous = "";
  for (const r of v.rows) {
    if (!keys(r, "employee_id evidence recorded_unoccupied_duration_us recorded_utilization_ratio") || typeof r.employee_id !== "string"
      || !r.employee_id || r.employee_id.length > 80 || r.employee_id.trim() !== r.employee_id || r.employee_id <= previous
      || !validOccupation(r.evidence, institute, r.employee_id, day, expected.start, expected.end, timezone, 0, 1)
      || certificationInstant(r.evidence.work_hours.generated_at) !== now) return false;
    previous = r.employee_id;
    const evidence = r.evidence;
    const w = workDuration(evidence.work_hours.known_union_duration_us)!, b = workDuration(evidence.covered_busy_duration_us)!;
    const incomplete = occupationDiagnosticKeys.some(k => k !== "retained" && evidence.diagnostics[k] > 0);
    const ready = r.evidence.work_hours.recorded_duration_us !== null && !incomplete;
    if (r.recorded_unoccupied_duration_us !== (ready ? String(w-b) : null)
      || (ready && w > 0n ? !ratio(r.recorded_utilization_ratio, b, w) : r.recorded_utilization_ratio !== null)) return false;
    rowWork += w; rowBusy += b; rowOutside += workDuration(r.evidence.outside_recorded_work_duration_us)!;
    missing += Number(r.evidence.work_hours.recorded_duration_us === null); uncertain += Number(incomplete);
  }
  if (rowWork > work || rowBusy > busy || rowOutside > outside || missing > v.employees_without_usable_hours || uncertain > v.employees_with_uncertain_activity) return false;
  return offset !== 0 || v.employee_count > 20 || (rowWork === work && rowBusy === busy && rowOutside === outside
    && missing === v.employees_without_usable_hours && uncertain === v.employees_with_uncertain_activity);
}
