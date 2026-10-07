import { certificationInstant as instant, certificationDate, validRevokeTerms, type RevokeTerms } from "./certification-utils";
export type RebookingTerms = RevokeTerms & { source_kind: "session" | "appointment"; source_id: string; target_appointment_id: string };
export type ExecutionCapture = { kind: "session" | "appointment"; id: string; employee_id: string; service_id: string; customer_id: string; actual_start: string; actual_end: string };
export type BookingCapture = { appointment_id: string; creation_event_id: string; created_at: string; original_start: string; original_end: string; current_start: string; current_end: string };
export type RebookingCancellation = RevokeTerms & { id: string; institute_id: string; rebooking_id: string; actor_id: string; created_at: string };
export type Rebooking = RebookingTerms & { id: string; institute_id: string; employee_id: string; actor_id: string; created_at: string;
  source_capture: ExecutionCapture; booking_capture: BookingCapture; cancellation: RebookingCancellation | null };
export type RebookingIntent = { type: "create"; terms: RebookingTerms } | { type: "cancel"; original: Rebooking; terms: RevokeTerms };
export const rebookingStates = ["cancelled_declaration", "future_recording", "unknown_target", "cancelled_booking", "no_show", "booked_return", "completed_return"] as const;
export type RebookingState = typeof rebookingStates[number];
export type RebookingDayRow = { original: Rebooking; target_status: string | null; target_customer_id: string | null; actual_start: string | null; actual_end: string | null; state: RebookingState };
type Page = { offset: number; limit: number; total: number };
export type RebookingPage = { institute_id: string; employee_id: string; generated_at: string; page: Page; rows: Rebooking[] };
export type RebookingDay = { institute_id: string; employee_id: string; day: string; timezone: string; start: string; end: string; generated_at: string;
  basis: "declaration_recorded_at"; page: Page; rows: RebookingDayRow[]; counts: Record<RebookingState, number>; complete_attribution: false; conversion_basis_points: null };
const text = (v: unknown, max = 80): v is string => typeof v === "string" && !!v && v.trim() === v && v.length <= max;
const count = (v: unknown): v is number => Number.isSafeInteger(v) && (v as number) >= 0;
export function validRebookingTerms(v: unknown): v is RebookingTerms {
  const r = v as RebookingTerms;
  return validRevokeTerms(r) && ["session", "appointment"].includes(r.source_kind) && text(r.source_id) && text(r.target_appointment_id)
    && (r.source_kind !== "appointment" || r.source_id !== r.target_appointment_id);
}
export function validRebookingCancellation(v: unknown, institute: string, original?: string): v is RebookingCancellation {
  const r = v as RebookingCancellation;
  return validRevokeTerms(r) && r.institute_id === institute && text(r.id) && text(r.rebooking_id) && (!original || r.rebooking_id === original)
    && text(r.actor_id, 160) && instant(r.created_at) !== undefined;
}
export function validRebooking(v: unknown, institute: string, employee?: string): v is Rebooking {
  const r = v as Rebooking, s = r?.source_capture, b = r?.booking_capture;
  if (!validRebookingTerms(r) || r.institute_id !== institute || !text(r.id) || !text(r.employee_id) || employee && r.employee_id !== employee
    || !text(r.actor_id, 160) || !s || !b || s.kind !== r.source_kind || s.id !== r.source_id || s.employee_id !== r.employee_id
    || !text(s.service_id) || !text(s.customer_id) || b.appointment_id !== r.target_appointment_id || !text(b.creation_event_id)
    || r.cancellation !== null && !validRebookingCancellation(r.cancellation, institute, r.id)) return false;
  const first = instant(s.actual_start), last = instant(s.actual_end), created = instant(b.created_at), recorded = instant(r.created_at);
  const originalFirst = instant(b.original_start), originalLast = instant(b.original_end), currentFirst = instant(b.current_start), currentLast = instant(b.current_end);
  return first !== undefined && last !== undefined && last > first && created !== undefined && created >= last && recorded !== undefined && recorded >= created
    && originalFirst !== undefined && originalLast !== undefined && originalLast > originalFirst && originalFirst > created
    && currentFirst !== undefined && currentLast !== undefined && currentLast > currentFirst && currentFirst > last;
}
export const matchesRebooking = (r: Rebooking, t: RebookingTerms, actor: string) => r.actor_id === actor && r.source_kind === t.source_kind
  && r.source_id === t.source_id && r.target_appointment_id === t.target_appointment_id && r.reason === t.reason && r.idempotency_key === t.idempotency_key;
export function sameRebookingOriginal(a: Rebooking, b: Rebooking) {
  const s = a.source_capture, t = b.source_capture, c = a.booking_capture, d = b.booking_capture;
  return a.id === b.id && a.institute_id === b.institute_id && a.employee_id === b.employee_id && matchesRebooking(a, b, b.actor_id)
    && instant(a.created_at) === instant(b.created_at) && s.kind === t.kind && s.id === t.id && s.employee_id === t.employee_id
    && s.service_id === t.service_id && s.customer_id === t.customer_id && instant(s.actual_start) === instant(t.actual_start) && instant(s.actual_end) === instant(t.actual_end)
    && c.appointment_id === d.appointment_id && c.creation_event_id === d.creation_event_id
    && (["created_at", "original_start", "original_end", "current_start", "current_end"] as const).every(k => instant(c[k]) === instant(d[k]));
}
export function validRebookingIntent(v: unknown, institute: string): v is RebookingIntent {
  const r = v as RebookingIntent;
  return !!r && (r.type === "create" ? validRebookingTerms(r.terms) : r.type === "cancel" && validRebooking(r.original, institute)
    && r.original.cancellation === null && validRevokeTerms(r.terms));
}
function page(p: Page, rows: unknown[], offset: number) {
  return !!p && p.offset === offset && p.limit === 20 && count(p.total) && Array.isArray(rows) && rows.length === Math.min(20, Math.max(0, p.total-offset));
}
function uniqueActive(rows: Rebooking[]) {
  const active = rows.filter(s => s.cancellation === null);
  return new Set(active.map(s => `${s.source_kind}:${s.source_id}`)).size === active.length
    && new Set(active.map(s => s.target_appointment_id)).size === active.length;
}
export function validRebookingPage(v: unknown, institute: string, employee: string, offset: number): v is RebookingPage {
  const r = v as RebookingPage;
  return !!r && r.institute_id === institute && r.employee_id === employee && instant(r.generated_at) !== undefined && page(r.page, r.rows, offset)
    && new Set(r.rows.map(s => s?.id)).size === r.rows.length && r.rows.every(s => validRebooking(s, institute, employee)) && uniqueActive(r.rows);
}
function state(r: RebookingDayRow, now: bigint): RebookingState {
  if (r.original.cancellation) return "cancelled_declaration";
  if (instant(r.original.created_at)! > now) return "future_recording";
  if (!r.target_customer_id || r.target_customer_id !== r.original.source_capture.customer_id) return "unknown_target";
  if (r.target_status === "cancelled") return "cancelled_booking";
  if (r.target_status === "no_show") return "no_show";
  if (["scheduled", "confirmed", "arrived", "in_progress"].includes(r.target_status!)) return "booked_return";
  const first = instant(r.actual_start), last = instant(r.actual_end);
  return r.target_status === "completed" && first !== undefined && last !== undefined && last > first && last <= now
    && first >= instant(r.original.booking_capture.created_at)! && first > instant(r.original.source_capture.actual_end)! ? "completed_return" : "unknown_target";
}
export function validRebookingDay(v: unknown, institute: string, employee: string, day: string, start: string, end: string, zone: string, offset: number): v is RebookingDay {
  const r = v as RebookingDay, from = instant(start), until = instant(end), now = instant(r?.generated_at);
  if (!r || r.institute_id !== institute || r.employee_id !== employee || r.day !== day || !certificationDate(day) || r.timezone !== zone
    || from === undefined || until === undefined || until < from || instant(r.start) !== from || instant(r.end) !== until || now === undefined
    || r.basis !== "declaration_recorded_at" || r.complete_attribution !== false || r.conversion_basis_points !== null || !page(r.page, r.rows, offset)
    || !r.counts || Object.keys(r.counts).length !== rebookingStates.length || !rebookingStates.every(k => count(r.counts[k]))
    || rebookingStates.reduce((sum, k) => sum+r.counts[k], 0) !== r.page.total || new Set(r.rows.map(s => s?.original?.id)).size !== r.rows.length) return false;
  const seen = Object.fromEntries(rebookingStates.map(k => [k, 0])) as RebookingDay["counts"];
  for (const s of r.rows) {
    if (!s || !validRebooking(s.original, institute, employee) || instant(s.original.created_at)! < from || instant(s.original.created_at)! >= until
      || s.target_status !== null && !text(s.target_status, 40) || s.target_customer_id !== null && !text(s.target_customer_id)
      || s.actual_start !== null && instant(s.actual_start) === undefined || s.actual_end !== null && instant(s.actual_end) === undefined
      || s.state !== state(s, now)) return false;
    seen[s.state]++;
  }
  return uniqueActive(r.rows.map(s => s.original)) && rebookingStates.every(k => seen[k] <= r.counts[k] && (offset || r.page.total > 20 || seen[k] === r.counts[k]));
}
