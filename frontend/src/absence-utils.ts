export type AbsenceTerms = { employee_id: string; kind: "absence" | "leave"; start_time: string; end_time: string; reason: string; idempotency_key: string };
export type CancelTerms = { reason: string; idempotency_key: string };
export type AbsenceCancellation = CancelTerms & { id: string; institute_id: string; absence_id: string; actor_id: string; created_at: string };
export type Absence = AbsenceTerms & { id: string; institute_id: string; actor_id: string; created_at: string; cancellation: AbsenceCancellation | null };
export type AbsenceIntent = { type: "create"; terms: AbsenceTerms } | { type: "cancel"; absence_id: string; terms: CancelTerms };
const text = (value: unknown, max: number): value is string => typeof value === "string" && value === value.trim() && value.length > 0 && value.length <= max;
const instant = (value: unknown): value is string => typeof value === "string" && /(?:Z|[+-]\d{2}:\d{2})$/.test(value) && Number.isFinite(Date.parse(value));
export function validCancelTerms(value: unknown): value is CancelTerms {
  const row = value as CancelTerms;
  return !!row && text(row.reason, 240) && text(row.idempotency_key, 120);
}
export function validAbsenceTerms(value: unknown): value is AbsenceTerms {
  const row = value as AbsenceTerms;
  return validCancelTerms(row) && text(row.employee_id, 80) && ["absence", "leave"].includes(row.kind)
    && instant(row.start_time) && instant(row.end_time) && Date.parse(row.end_time) > Date.parse(row.start_time);
}
export function validCancellation(value: unknown, institute: string, absence?: string): value is AbsenceCancellation {
  const row = value as AbsenceCancellation;
  return validCancelTerms(row) && text(row.id, 80) && row.institute_id === institute && text(row.absence_id, 80)
    && (!absence || row.absence_id === absence) && text(row.actor_id, 160) && instant(row.created_at);
}
export function validAbsence(value: unknown, institute: string): value is Absence {
  const row = value as Absence;
  return validAbsenceTerms(row) && text(row.id, 80) && row.institute_id === institute && text(row.actor_id, 160)
    && instant(row.created_at) && (row.cancellation === null || validCancellation(row.cancellation, institute, row.id));
}
export function validAbsenceIntent(value: unknown): value is AbsenceIntent {
  const row = value as AbsenceIntent;
  return !!row && (row.type === "create" ? validAbsenceTerms(row.terms)
    : row.type === "cancel" && text(row.absence_id, 80) && validCancelTerms(row.terms));
}
export const matchesAbsence = (row: Absence, terms: AbsenceTerms, actor: string) => row.actor_id === actor
  && row.employee_id === terms.employee_id && row.kind === terms.kind && row.reason === terms.reason
  && row.idempotency_key === terms.idempotency_key && Date.parse(row.start_time) === Date.parse(terms.start_time)
  && Date.parse(row.end_time) === Date.parse(terms.end_time);
export const matchesCancellation = (row: AbsenceCancellation, absence: string, terms: CancelTerms, actor: string) =>
  row.actor_id === actor && row.absence_id === absence && row.reason === terms.reason && row.idempotency_key === terms.idempotency_key;
