import { instituteSlot, instituteBoundary } from "./institute-calendar";
export type EmployeeEvent = { source_kind: "appointment" | "session" | "absence"; id: string; status: string;
  service_id: string | null; service_name: string | null; start_time: string; end_time: string; actual_start_time: string | null;
  actual_end_time: string | null; absence_kind: "absence" | "leave" | null; reason: string | null; cancellation_id: string | null };
type Slot = { employee_id: string; institute_id: string; available_from: string | null; available_until: string | null; reason: string };
export type EmployeeDay = { institute_id: string; generated_at: string; employee: { id: string; first_name: string; status: string; skills: string[] };
  day: string; timezone: string; day_start: string; day_end: string;
  availability: { employee_id: string; institute_id: string; service_id: null; available: boolean; current_slot: Slot | null; upcoming_slots: Slot[] };
  event_page: { offset: number; limit: number; total: number }; events: EmployeeEvent[] };
const text = (value: unknown): value is string => typeof value === "string" && !!value.trim();
const instant = (value: unknown): value is string => text(value) && /(?:Z|[+-]\d{2}:\d{2})$/.test(value) && Number.isFinite(Date.parse(value));
const optionalInstant = (value: unknown) => value === null || instant(value);
const reasons = new Set(["available_now", "in_progress_session", "upcoming_appointment", "employee_pause", "employee_absent", "employee_offline", "busy_until", "session_overdue", "capacity_unknown", "skills_missing", "resource_capacity_unknown", "resource_reserved", "scheduled_absence"]);
export function validEmployeeDay(value: unknown, institute: string, employee: string, day: string, offset: number): value is EmployeeDay {
  const row = value as EmployeeDay;
  if (!row || row.institute_id !== institute || row.employee?.id !== employee || row.day !== day || !instant(row.generated_at)
    || !text(row.employee.first_name) || !text(row.employee.status) || !Array.isArray(row.employee.skills)
    || !row.employee.skills.every(text) || new Set(row.employee.skills).size !== row.employee.skills.length
    || !instant(row.day_start) || !instant(row.day_end) || Date.parse(row.day_end) < Date.parse(row.day_start)) return false;
  try { new Intl.DateTimeFormat("en", { timeZone: row.timezone }).format(new Date(row.day_start)); } catch { return false; }
  if (!text(row.timezone)) return false;
  const nextDay = new Date(Date.parse(`${day}T12:00:00Z`)+86400000);
  if (!Number.isFinite(nextDay.getTime())) return false;
  const nextCivil = nextDay.toISOString().slice(0, 10), afterNext = new Date(nextDay.getTime()+86400000).toISOString().slice(0, 10);
  const endCivil = instituteSlot(row.day_end, row.timezone)?.date;
  const expectedStart = instituteBoundary(day, 0, row.timezone);
  const expectedEnd = instituteBoundary(nextCivil, 0, row.timezone) ?? instituteBoundary(afterNext, 0, row.timezone);
  if (expectedStart !== undefined && Date.parse(row.day_start) !== expectedStart
    || expectedEnd !== undefined && Date.parse(row.day_end) !== expectedEnd) return false;
  if (endCivil !== nextCivil && (instituteBoundary(nextCivil, 0, row.timezone) !== undefined || endCivil !== afterNext)
    || Date.parse(row.day_start) !== Date.parse(row.day_end) && instituteSlot(row.day_start, row.timezone)?.date !== day) return false;
  const available = row.availability;
  const slot = (value: Slot | null) => value === null || !!value && value.employee_id === employee && value.institute_id === institute
    && optionalInstant(value.available_from) && optionalInstant(value.available_until) && reasons.has(value.reason)
    && (!value.available_from || !value.available_until || Date.parse(value.available_until) > Date.parse(value.available_from));
  if (!available || available.employee_id !== employee || available.institute_id !== institute || available.service_id !== null
    || typeof available.available !== "boolean" || !slot(available.current_slot) || !Array.isArray(available.upcoming_slots)
    || !available.upcoming_slots.every(value => value !== null && slot(value)) || available.available && (!available.current_slot?.available_from
      || Date.parse(available.current_slot.available_from) !== Date.parse(row.generated_at))) return false;
  const page = row.event_page;
  if (!page || page.offset !== offset || page.limit !== 50 || !Number.isSafeInteger(page.total) || page.total < 0
    || !Array.isArray(row.events) || row.events.length !== Math.min(50, Math.max(0, page.total-offset))) return false;
  const ids = new Set<string>();
  return row.events.every(event => {
    if (!event || !text(event.id) || !text(event.status) || !instant(event.start_time) || !instant(event.end_time)
      || Date.parse(event.end_time) <= Date.parse(event.start_time) || !optionalInstant(event.actual_start_time)
      || !optionalInstant(event.actual_end_time) || event.actual_start_time && event.actual_end_time
        && Date.parse(event.actual_end_time) < Date.parse(event.actual_start_time)) return false;
    const key = `${event.source_kind}:${event.id}`; if (ids.has(key)) return false; ids.add(key);
    const from = Date.parse(row.day_start), until = Date.parse(row.day_end);
    if (from === until) return false;
    const plannedOverlap = Date.parse(event.start_time) < until && Date.parse(event.end_time) > from;
    const actualOverlap = event.actual_start_time && Date.parse(event.actual_start_time) < until && (event.actual_end_time
      ? Date.parse(event.actual_end_time) > from : ["in_progress", "extended", "delayed"].includes(event.status));
    const openSession = event.source_kind === "session" && event.actual_end_time === null
      && ["planned", "in_progress", "extended", "delayed"].includes(event.status) && Date.parse(event.start_time) < until;
    if (!plannedOverlap && !actualOverlap && !openSession) return false;
    if (event.source_kind === "absence") return ["absence", "leave"].includes(event.absence_kind!) && text(event.reason)
      && event.service_id === null && event.service_name === null && event.actual_start_time === null && event.actual_end_time === null
      && (event.status === "cancelled" ? text(event.cancellation_id) : event.status === "recorded" && event.cancellation_id === null);
    return (event.source_kind === "appointment" ? ["scheduled", "confirmed", "arrived", "in_progress", "completed", "cancelled", "no_show"].includes(event.status)
      : event.source_kind === "session" && ["planned", "in_progress", "extended", "delayed", "completed", "cancelled"].includes(event.status)) && text(event.service_id)
      && (event.service_name === null || text(event.service_name))
      && event.absence_kind === null && event.reason === null && event.cancellation_id === null;
  });
}
