export type CertificationTerms = { employee_id: string; code: string; title: string; issuer: string; reference: string;
  issued_on: string | null; valid_from: string; valid_until: string | null; reason: string; idempotency_key: string };
export type RevokeTerms = { reason: string; idempotency_key: string };
export type CertificationRevocation = RevokeTerms & { id: string; institute_id: string; certification_id: string; actor_id: string; created_at: string };
export type Certification = CertificationTerms & { id: string; institute_id: string; actor_id: string; created_at: string; revocation: CertificationRevocation | null };
export type CertificationIntent = { type: "create"; terms: CertificationTerms } | { type: "revoke"; employee_id: string; certification_id: string; terms: RevokeTerms };
export type CertificationState = "not_yet_valid" | "in_validity_window" | "expired" | "revoked";
export type CertificationPage = { institute_id: string; employee_id: string; generated_at: string;
  page: { offset: number; limit: number; total: number }; rows: { certificate: Certification; state: CertificationState }[] };
const text = (value: unknown, max: number): value is string => typeof value === "string" && value === value.trim() && value.length > 0 && value.length <= max;
export function certificationInstant(value: unknown): bigint | undefined {
  if (typeof value !== "string") return;
  const match = /^(\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d)(?:\.(\d{1,6}))?(Z|[+-]\d{2}:\d{2})$/.exec(value);
  if (!match || !certificationDate(match[1].slice(0, 10))) return;
  const milliseconds = Date.parse(match[1]+match[3]);
  if (!Number.isFinite(milliseconds) || new Date(milliseconds).getUTCFullYear() < 1 || new Date(milliseconds).getUTCFullYear() > 9999) return;
  return BigInt(milliseconds)*1000n + BigInt((match[2] || "").padEnd(6, "0"));
}
export function certificationDate(value: unknown): value is string {
  if (typeof value !== "string" || !/^(?!0000)\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const date = new Date(`${value}T12:00:00Z`);
  return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === value;
}
export function validRevokeTerms(value: unknown): value is RevokeTerms {
  const row = value as RevokeTerms;
  return !!row && text(row.reason, 240) && text(row.idempotency_key, 120);
}
export function validCertificationTerms(value: unknown): value is CertificationTerms {
  const row = value as CertificationTerms;
  if (!validRevokeTerms(row) || !text(row.employee_id, 80) || !text(row.code, 64) || !text(row.title, 120)
    || !text(row.issuer, 120) || !text(row.reference, 160) || row.issued_on !== null && !certificationDate(row.issued_on)) return false;
  const start = certificationInstant(row.valid_from), end = certificationInstant(row.valid_until);
  return start !== undefined && (row.valid_until === null || end !== undefined && end > start);
}
export function validCertificationRevocation(value: unknown, institute: string, certificate?: string): value is CertificationRevocation {
  const row = value as CertificationRevocation;
  return validRevokeTerms(row) && text(row.id, 80) && row.institute_id === institute && text(row.certification_id, 80)
    && (!certificate || row.certification_id === certificate) && text(row.actor_id, 160) && certificationInstant(row.created_at) !== undefined;
}
export function validCertification(value: unknown, institute: string, employee?: string): value is Certification {
  const row = value as Certification;
  return validCertificationTerms(row) && row.institute_id === institute && (!employee || row.employee_id === employee)
    && text(row.id, 80) && text(row.actor_id, 160) && certificationInstant(row.created_at) !== undefined
    && (row.revocation === null || validCertificationRevocation(row.revocation, institute, row.id));
}
export function validCertificationIntent(value: unknown): value is CertificationIntent {
  const row = value as CertificationIntent;
  return !!row && (row.type === "create" ? validCertificationTerms(row.terms) : row.type === "revoke"
    && text(row.employee_id, 80) && text(row.certification_id, 80) && validRevokeTerms(row.terms));
}
export const certificationEmployee = (intent: CertificationIntent) => intent.type === "create" ? intent.terms.employee_id : intent.employee_id;
export const matchesCertification = (row: Certification, terms: CertificationTerms, actor: string) => row.actor_id === actor
  && row.employee_id === terms.employee_id && row.code === terms.code && row.title === terms.title && row.issuer === terms.issuer
  && row.reference === terms.reference && row.issued_on === terms.issued_on && row.reason === terms.reason && row.idempotency_key === terms.idempotency_key
  && certificationInstant(row.valid_from) === certificationInstant(terms.valid_from)
  && (row.valid_until === null ? terms.valid_until === null : certificationInstant(row.valid_until) === certificationInstant(terms.valid_until));
export const matchesRevocation = (row: CertificationRevocation, certificate: string, terms: RevokeTerms, actor: string) =>
  row.certification_id === certificate && row.actor_id === actor && row.reason === terms.reason && row.idempotency_key === terms.idempotency_key;
export function declaredCertificationState(row: Certification, at: string): CertificationState {
  if (row.revocation) return "revoked";
  const now = certificationInstant(at)!;
  if (certificationInstant(row.valid_from)! > now) return "not_yet_valid";
  if (row.valid_until !== null && certificationInstant(row.valid_until)! <= now) return "expired";
  return "in_validity_window";
}
export function validCertificationPage(value: unknown, institute: string, employee: string, offset: number): value is CertificationPage {
  const row = value as CertificationPage;
  if (!row || row.institute_id !== institute || row.employee_id !== employee || certificationInstant(row.generated_at) === undefined
    || !row.page || row.page.offset !== offset || row.page.limit !== 50 || !Number.isSafeInteger(row.page.total) || row.page.total < 0
    || !Array.isArray(row.rows) || row.rows.length !== Math.min(50, Math.max(0, row.page.total-offset))) return false;
  return new Set(row.rows.map(value => value?.certificate?.id)).size === row.rows.length && row.rows.every(value => !!value
    && validCertification(value.certificate, institute, employee) && value.state === declaredCertificationState(value.certificate, row.generated_at));
}
