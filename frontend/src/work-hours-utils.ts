import { certificationInstant, validRevokeTerms, type RevokeTerms } from "./certification-utils";
export type WorkTerms = RevokeTerms & { employee_id: string; start_time: string; end_time: string };
export type WorkCancellation = RevokeTerms & { id: string; institute_id: string; work_interval_id: string; actor_id: string; created_at: string };
export type WorkInterval = WorkTerms & { id: string; institute_id: string; actor_id: string; created_at: string; cancellation: WorkCancellation | null };
export type WorkIntent = { type: "create"; terms: WorkTerms } | { type: "cancel"; original: WorkInterval; terms: RevokeTerms };
export type WorkPage = { institute_id: string; employee_id: string; generated_at: string; page: { offset: number; limit: number; total: number }; rows: WorkInterval[] };
export type WorkHourSource = { interval: WorkInterval; clipped_start: string; clipped_end: string; duration_us: string; exclusion: "cancelled" | "future_end" | null };
export type WorkHours = { institute_id: string; employee_id: string; day: string; timezone: string; start: string; end: string; generated_at: string;
  page: { offset: number; limit: number; total: number }; rows: WorkHourSource[]; active_sources: number; future_end_sources: number; overlap_sources: number;
  known_declared_duration_us: string; known_union_duration_us: string; recorded_duration_us: string | null; complete_attendance: false };
const text = (v: unknown, max: number): v is string => typeof v === "string" && !!v && v.trim() === v && v.length <= max;
const count = (v: unknown): v is number => Number.isSafeInteger(v) && (v as number) >= 0;
export function workDuration(v: unknown): bigint | undefined {
  if (typeof v === "string" && /^(?:0|[1-9]\d{0,39})$/.test(v)) return BigInt(v);
}
export function validWorkTerms(v: unknown): v is WorkTerms {
  const r = v as WorkTerms, first = certificationInstant(r?.start_time), last = certificationInstant(r?.end_time);
  return validRevokeTerms(r) && text(r.employee_id, 80) && first !== undefined && last !== undefined && last > first;
}
export function validWorkCancellation(v: unknown, institute: string, interval?: string): v is WorkCancellation {
  const r = v as WorkCancellation;
  return validRevokeTerms(r) && r.institute_id === institute && text(r.id, 80) && text(r.work_interval_id, 80)
    && (!interval || r.work_interval_id === interval) && text(r.actor_id, 160) && certificationInstant(r.created_at) !== undefined;
}
export function validWorkInterval(v: unknown, institute: string, employee?: string): v is WorkInterval {
  const r = v as WorkInterval;
  return validWorkTerms(r) && r.institute_id === institute && (!employee || r.employee_id === employee) && text(r.id, 80)
    && text(r.actor_id, 160) && certificationInstant(r.created_at) !== undefined
    && (r.cancellation === null || validWorkCancellation(r.cancellation, institute, r.id));
}
export function validWorkIntent(v: unknown, institute: string): v is WorkIntent {
  const r = v as WorkIntent;
  return !!r && (r.type === "create" ? validWorkTerms(r.terms) : r.type === "cancel" && validWorkInterval(r.original, institute)
    && r.original.cancellation === null && validRevokeTerms(r.terms));
}
export const matchesWork = (r: WorkInterval, t: WorkTerms, actor: string) => r.actor_id === actor && r.employee_id === t.employee_id
  && certificationInstant(r.start_time) === certificationInstant(t.start_time) && certificationInstant(r.end_time) === certificationInstant(t.end_time)
  && r.reason === t.reason && r.idempotency_key === t.idempotency_key;
export const sameWorkOriginal = (a: WorkInterval, b: WorkInterval) => a.id === b.id && a.institute_id === b.institute_id
  && matchesWork(a, b, b.actor_id) && certificationInstant(a.created_at) === certificationInstant(b.created_at);
export function validWorkPage(v: unknown, institute: string, employee: string, offset: number): v is WorkPage {
  const r = v as WorkPage;
  return !!r && r.institute_id === institute && r.employee_id === employee && certificationInstant(r.generated_at) !== undefined
    && !!r.page && r.page.offset === offset && r.page.limit === 20 && count(r.page.total) && Array.isArray(r.rows)
    && r.rows.length === Math.min(20, Math.max(0, r.page.total-offset)) && new Set(r.rows.map(v => v?.id)).size === r.rows.length
    && r.rows.every(v => validWorkInterval(v, institute, employee));
}
export function validWorkHours(v: unknown, institute: string, employee: string, day: string, start: string, end: string, zone: string, offset: number): v is WorkHours {
  const r = v as WorkHours, from = certificationInstant(start), until = certificationInstant(end), now = certificationInstant(r?.generated_at);
  if (!r || r.institute_id !== institute || r.employee_id !== employee || r.day !== day || r.timezone !== zone
    || from === undefined || until === undefined || until < from || now === undefined || certificationInstant(r.start) !== from || certificationInstant(r.end) !== until
    || r.complete_attendance !== false || !r.page || r.page.offset !== offset || r.page.limit !== 20 || !count(r.page.total)
    || !count(r.active_sources) || r.active_sources > r.page.total || !count(r.future_end_sources) || r.future_end_sources > r.active_sources
    || !count(r.overlap_sources) || r.overlap_sources > Math.max(0, r.active_sources-r.future_end_sources-1)
    || !Array.isArray(r.rows) || r.rows.length !== Math.min(20, Math.max(0, r.page.total-offset))
    || new Set(r.rows.map(s => s?.interval?.id)).size !== r.rows.length) return false;
  const declared = workDuration(r.known_declared_duration_us), union = workDuration(r.known_union_duration_us);
  if (declared === undefined || union === undefined || union > declared || union > until-from
    || (!r.overlap_sources && union !== declared) || (r.overlap_sources > 0 && union >= declared)
    || (from === until && r.page.total !== 0) || (r.active_sources === r.future_end_sources ? union !== 0n : union === 0n)
    || (r.future_end_sources || !r.active_sources ? r.recorded_duration_us !== null : workDuration(r.recorded_duration_us) !== union)) return false;
  let seenActive = 0, seenFuture = 0, seenDeclared = 0n, seenUnion = 0n, seenOverlap = 0, previousEnd: bigint | undefined;
  let previousStart: bigint | undefined;
  for (const s of r.rows) {
    if (!s || !validWorkInterval(s.interval, institute, employee)) return false;
    const first = certificationInstant(s.interval.start_time)!, last = certificationInstant(s.interval.end_time)!;
    if (previousStart !== undefined && first < previousStart) return false;
    previousStart = first;
    const clippedFirst = first > from ? first : from, clippedLast = last < until ? last : until;
    if (clippedLast <= clippedFirst || certificationInstant(s.clipped_start) !== clippedFirst || certificationInstant(s.clipped_end) !== clippedLast
      || workDuration(s.duration_us) !== clippedLast-clippedFirst) return false;
    const exclusion = s.interval.cancellation ? "cancelled" : last > now ? "future_end" : null;
    if (s.exclusion !== exclusion) return false;
    if (exclusion === "cancelled") continue;
    seenActive++;
    if (exclusion === "future_end") { seenFuture++; continue; }
    seenDeclared += clippedLast-clippedFirst;
    if (previousEnd !== undefined && clippedFirst < previousEnd) seenOverlap++;
    const uncovered = previousEnd !== undefined && previousEnd > clippedFirst ? previousEnd : clippedFirst;
    if (clippedLast > uncovered) seenUnion += clippedLast-uncovered;
    previousEnd = previousEnd !== undefined && previousEnd > clippedLast ? previousEnd : clippedLast;
  }
  if (seenActive > r.active_sources || seenFuture > r.future_end_sources || seenDeclared > declared || seenUnion > union || seenOverlap > r.overlap_sources) return false;
  return offset || r.page.total > 20 ? true : seenActive === r.active_sources && seenFuture === r.future_end_sources
    && seenDeclared === declared && seenUnion === union && seenOverlap === r.overlap_sources;
}
export function formatWorkDuration(value: string) {
  const us = workDuration(value)!;
  const fraction = us%1000000n;
  return `${us/3600000000n} h ${String(us/60000000n%60n).padStart(2, "0")} min ${String(us/1000000n%60n).padStart(2, "0")}${fraction ? `,${String(fraction).padStart(6, "0")}` : ""} s`;
}
