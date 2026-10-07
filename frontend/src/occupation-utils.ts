import { certificationInstant } from "./certification-utils";
import { validWorkHours, workDuration, type WorkHours } from "./work-hours-utils";
import { validOccupationTotals, occupationDiagnosticKeys, type OccupationTotals } from "./occupation-math";
export type OccupationSource = { kind: "session" | "appointment"; id: string; service_id: string; status: string;
  actual_start: string | null; actual_end: string | null; exclusion: "missing_start" | "missing_end" | "invalid_interval" | "future_end" | "unfinalized" | null;
  clipped_start: string | null; clipped_end: string | null; duration_us: string | null };
export type Occupation = OccupationTotals & { work_hours: WorkHours; page: { offset: number; limit: number; total: number };
  rows: OccupationSource[]; diagnostics: Record<typeof occupationDiagnosticKeys[number], number> };
const text = (v: unknown): v is string => typeof v === "string" && !!v && v.trim() === v && v.length <= 80;
function union(values: [bigint, bigint][]) {
  const merged: [bigint, bigint][] = [];
  for (const value of values.sort((a, b) => a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0)) {
    const old = merged[merged.length-1];
    if (old && value[0] <= old[1]) { if (value[1] > old[1]) old[1] = value[1]; }
    else merged.push([...value]);
  }
  return merged;
}
export function validOccupation(v: unknown, institute: string, employee: string, day: string, start: string, end: string, zone: string, offset: number): v is Occupation {
  const r = v as Occupation;
  if (!r || !validWorkHours(r.work_hours, institute, employee, day, start, end, zone, 0) || !r.page || r.page.offset !== offset
    || r.page.limit !== 20 || !Number.isSafeInteger(r.page.total) || r.page.total < 0 || !Array.isArray(r.rows)
    || r.rows.length !== Math.min(20, Math.max(0, r.page.total-offset))
    || !validOccupationTotals(r, r.work_hours.recorded_duration_us, r.work_hours.known_union_duration_us, r.diagnostics, r.page.total)
    || new Set(r.rows.map(s => `${s?.kind}:${s?.id}`)).size !== r.rows.length) return false;
  const from = certificationInstant(start)!, until = certificationInstant(end)!, now = certificationInstant(r.work_hours.generated_at)!;
  if (from === until && r.page.total) return false;
  const seen = Object.fromEntries(occupationDiagnosticKeys.map(k => [k, 0])) as Occupation["diagnostics"];
  for (const s of r.rows) {
    if (!s || !["session", "appointment"].includes(s.kind) || !text(s.id) || !text(s.service_id)
      || !(s.kind === "session" ? ["completed", "in_progress", "extended", "delayed"] : ["completed", "in_progress"]).includes(s.status)) return false;
    const first = certificationInstant(s.actual_start), last = certificationInstant(s.actual_end);
    if (s.actual_start !== null && first === undefined || s.actual_end !== null && last === undefined) return false;
    if (s.kind === "session" && first === undefined) return false;
    const candidate = first !== undefined ? first < until && (last === undefined || last > from || last <= first && first >= from)
      : last !== undefined && last > from && last <= until;
    if (!candidate) return false;
    const why = first === undefined ? "missing_start" : last === undefined ? "missing_end" : last <= first ? "invalid_interval"
      : last > now ? "future_end" : s.status !== "completed" ? "unfinalized" : null;
    if (s.exclusion !== why) return false;
    seen[why || "retained"]++;
    if (why !== null) { if (s.clipped_start !== null || s.clipped_end !== null || s.duration_us !== null) return false; }
    else {
      const clippedFirst = first! > from ? first! : from, clippedLast = last! < until ? last! : until;
      if (certificationInstant(s.clipped_start) !== clippedFirst || certificationInstant(s.clipped_end) !== clippedLast
        || workDuration(s.duration_us) !== clippedLast-clippedFirst) return false;
    }
  }
  if (!occupationDiagnosticKeys.every(k => seen[k] <= r.diagnostics[k] && (offset || r.page.total > 20 || seen[k] === r.diagnostics[k]))) return false;
  if (!offset && r.page.total <= 20) {
    const busy = union(r.rows.filter(s => s.exclusion === null).map(s => [certificationInstant(s.clipped_start)!, certificationInstant(s.clipped_end)!]));
    if (busy.reduce((sum, [a, b]) => sum+b-a, 0n) !== workDuration(r.known_busy_duration_us)) return false;
    if (r.work_hours.page.total <= 20) {
      const work = union(r.work_hours.rows.filter(s => s.exclusion === null).map(s => [certificationInstant(s.clipped_start)!, certificationInstant(s.clipped_end)!]));
      let covered = 0n;
      for (const a of work) for (const b of busy) {
        const first = a[0] > b[0] ? a[0] : b[0], last = a[1] < b[1] ? a[1] : b[1];
        if (last > first) covered += last-first;
      }
      if (covered !== workDuration(r.covered_busy_duration_us)) return false;
    }
  }
  return true;
}
