import { certificationInstant as instant, certificationDate } from "./certification-utils";
import type { ExecutionCapture, BookingCapture } from "./rebooking-utils";
type Page = { offset: number; limit: number; total: number };
export type SourceChoice = { kind: "session" | "appointment"; id: string; service_id: string; actual_start: string | null; actual_end: string;
  customer_id: string | null; customer_known: boolean; already_attributed: boolean; exclusion: "invalid_execution" | "future_end" | "unknown_customer" | "already_attributed" | null; capture: ExecutionCapture | null };
export type SourceChoices = { institute_id: string; employee_id: string; day: string; timezone: string; start: string; end: string; generated_at: string;
  basis: "actual_completion_day"; complete_sources: false; page: Page; rows: SourceChoice[] };
export type TargetChoice = { id: string; employee_id: string; service_id: string; status: string; customer_id: string; booked_start: string | null; booked_end: string | null;
  creation_events: number; already_attributed: boolean; exclusion: "already_attributed" | "invalid_booking" | null; capture: BookingCapture | null };
export type TargetChoices = { institute_id: string; generated_at: string; source: ExecutionCapture; page: Page; rows: TargetChoice[] };
const text = (v: unknown): v is string => typeof v === "string" && !!v && v.trim() === v && v.length <= 80;
function page(p: Page, rows: unknown[], offset: number) {
  return !!p && p.offset === offset && p.limit === 20 && Number.isSafeInteger(p.total) && p.total >= 0 && Array.isArray(rows)
    && rows.length === Math.min(20, Math.max(0, p.total-offset));
}
export function sameExecution(a: ExecutionCapture, b: ExecutionCapture) {
  return a.kind === b.kind && a.id === b.id && a.employee_id === b.employee_id && a.service_id === b.service_id && a.customer_id === b.customer_id
    && instant(a.actual_start) === instant(b.actual_start) && instant(a.actual_end) === instant(b.actual_end);
}
export function validSourceChoices(v: unknown, institute: string, employee: string, day: string, start: string, end: string, zone: string, offset: number): v is SourceChoices {
  const r = v as SourceChoices, from = instant(start), until = instant(end), now = instant(r?.generated_at);
  if (!r || r.institute_id !== institute || r.employee_id !== employee || r.day !== day || !certificationDate(day) || r.timezone !== zone
    || r.basis !== "actual_completion_day" || r.complete_sources !== false || from === undefined || until === undefined || until < from
    || instant(r.start) !== from || instant(r.end) !== until || now === undefined || !page(r.page, r.rows, offset)
    || new Set(r.rows.map(s => `${s?.kind}:${s?.id}`)).size !== r.rows.length) return false;
  return r.rows.every(s => {
    if (!s || !["session", "appointment"].includes(s.kind) || !text(s.id) || !text(s.service_id) || typeof s.customer_known !== "boolean"
      || typeof s.already_attributed !== "boolean" || s.customer_id !== null && !text(s.customer_id) || s.customer_known && !s.customer_id) return false;
    const first = instant(s.actual_start), last = instant(s.actual_end);
    if (last === undefined || last < from || last >= until || s.actual_start !== null && first === undefined || s.kind === "session" && first === undefined) return false;
    const why = first === undefined || last <= first ? "invalid_execution" : last > now ? "future_end" : !s.customer_known ? "unknown_customer" : s.already_attributed ? "already_attributed" : null;
    if (why !== s.exclusion) return false;
    if (why !== null) return s.capture === null;
    const c = s.capture;
    return !!c && c.kind === s.kind && c.id === s.id && c.employee_id === employee && c.service_id === s.service_id && c.customer_id === s.customer_id
      && instant(c.actual_start) === first && instant(c.actual_end) === last;
  });
}
export function validTargetChoices(v: unknown, institute: string, source: ExecutionCapture, offset: number): v is TargetChoices {
  const r = v as TargetChoices, now = instant(r?.generated_at);
  if (!r || r.institute_id !== institute || now === undefined || !r.source || !sameExecution(r.source, source) || instant(source.actual_end) === undefined
    || instant(source.actual_start) === undefined || instant(source.actual_end)! <= instant(source.actual_start)! || instant(source.actual_end)! > now
    || !page(r.page, r.rows, offset) || new Set(r.rows.map(s => s?.id)).size !== r.rows.length) return false;
  return r.rows.every(s => {
    if (!s || !text(s.id) || !text(s.employee_id) || !text(s.service_id) || s.customer_id !== source.customer_id
      || !["scheduled", "confirmed", "arrived", "in_progress", "completed"].includes(s.status) || typeof s.already_attributed !== "boolean"
      || !Number.isSafeInteger(s.creation_events) || s.creation_events < 0 || s.booked_start !== null && instant(s.booked_start) === undefined
      || s.booked_end !== null && instant(s.booked_end) === undefined) return false;
    if (s.already_attributed) return s.exclusion === "already_attributed" && s.capture === null;
    if (s.exclusion === "invalid_booking") return s.capture === null;
    const c = s.capture, created = instant(c?.created_at), first = instant(c?.original_start), last = instant(c?.original_end), currentFirst = instant(s.booked_start), currentLast = instant(s.booked_end);
    return s.exclusion === null && s.creation_events === 1 && !!c && text(c.creation_event_id) && c.appointment_id === s.id
      && (source.kind !== "appointment" || source.id !== s.id) && created !== undefined && created >= instant(source.actual_end)! && created <= now
      && first !== undefined && last !== undefined && last > first && first > created && currentFirst !== undefined && currentLast !== undefined
      && currentLast > currentFirst && currentFirst > instant(source.actual_end)! && instant(c.current_start) === currentFirst && instant(c.current_end) === currentLast;
  });
}
