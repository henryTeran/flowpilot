import { certificationInstant as instant } from "./certification-utils";
import { revenueOriginalFingerprint } from "./revenue-scenario-utils";

export type WaitlistWindow = { start: string; end: string };
export type WaitlistDemand = { institute_id: string; customer_id: string; service_id: string; declared_at: string;
  duration_minutes: number; availability: WaitlistWindow[]; allowed_employee_ids: string[];
  constraints_review: "confirmed" | "unknown"; availability_evidence: string; constraints_evidence: string | null };
export type WaitlistOriginal = { id: string; institute_id: string; actor_id: string; created_at: string; idempotency_key: string; reason: string;
  demand: WaitlistDemand; source: { customer_id: string; registered_at: string; service_id: string; duration_minutes: number; allowed_employee_ids: string[] };
  state: "declared_only"; action: "no_booking_or_contact" };
export type WaitlistEnvelope = { original: WaitlistOriginal; fingerprint: string };
export type WaitlistOriginalAudit = { institute_id: string; captured_at: string; offset: number; limit: number; total: number;
  originals: WaitlistEnvelope[]; basis: "verified_retained_declarations_not_active_waitlist" };
export type WaitlistRequest = Omit<WaitlistDemand, "institute_id" | "declared_at"> & { reason: string; idempotency_key: string };

const keys = (v: unknown, names: string): v is Record<string, unknown> => !!v && typeof v === "object" && !Array.isArray(v)
  && Object.keys(v).sort().join(" ") === names.split(" ").sort().join(" ");
const text = (v: unknown, max: number, min = 1): v is string => typeof v === "string" && v.trim() === v
  && Array.from(v).length >= min && Array.from(v).length <= max;
const id = (v: unknown): v is string => text(v, 80) && !/[\x00-\x1f]/.test(v);
const count = (v: unknown): v is number => typeof v === "number" && Number.isSafeInteger(v) && v >= 0;
const ids = (v: unknown): v is string[] => Array.isArray(v) && v.length <= 100 && v.every(id) && new Set(v).size === v.length;
export function validWaitlistRequest(v: unknown): v is WaitlistRequest {
  if (!keys(v, "customer_id service_id duration_minutes availability allowed_employee_ids constraints_review availability_evidence constraints_evidence reason idempotency_key")
    || !id(v.customer_id) || !id(v.service_id) || !count(v.duration_minutes) || v.duration_minutes < 1 || v.duration_minutes > 1440
    || !ids(v.allowed_employee_ids) || !text(v.reason, 240, 3) || !text(v.idempotency_key, 120)
    || /[\x00-\x1f]/.test(v.idempotency_key) || !text(v.availability_evidence, 240, 3)
    || !["confirmed", "unknown"].includes(String(v.constraints_review))
    || (v.constraints_review === "confirmed" ? !text(v.constraints_evidence, 240, 3) : v.constraints_evidence !== null)
    || !Array.isArray(v.availability) || v.availability.length < 1 || v.availability.length > 64) return false;
  let previous: bigint | undefined;
  for (const window of v.availability) {
    if (!keys(window, "start end")) return false;
    const start = instant(window.start), end = instant(window.end);
    if (start === undefined || end === undefined || start >= end || previous !== undefined && start < previous) return false;
    previous = end;
  }
  return true;
}
export function matchesWaitlistReceipt(e: WaitlistEnvelope, request: WaitlistRequest, actor: string): boolean {
  const original = e.original, demand = original.demand;
  return original.actor_id === actor && original.reason === request.reason && original.idempotency_key === request.idempotency_key
    && demand.customer_id === request.customer_id && demand.service_id === request.service_id && demand.duration_minutes === request.duration_minutes
    && demand.constraints_review === request.constraints_review && demand.constraints_evidence === request.constraints_evidence
    && demand.availability_evidence === request.availability_evidence && demand.allowed_employee_ids.length === request.allowed_employee_ids.length
    && demand.allowed_employee_ids.every((value, index) => value === request.allowed_employee_ids[index])
    && demand.availability.length === request.availability.length && demand.availability.every((window, index) =>
      instant(window.start) === instant(request.availability[index].start) && instant(window.end) === instant(request.availability[index].end));
}
export function validWaitlistOriginalShape(v: unknown, institute: string): v is WaitlistOriginal {
  if (!keys(v, "id institute_id actor_id created_at idempotency_key reason demand source state action")
    || !id(v.id) || v.institute_id !== institute || !text(v.actor_id, 160) || /[\x00-\x1f]/.test(v.actor_id)
    || !text(v.idempotency_key, 120) || /[\x00-\x1f]/.test(v.idempotency_key) || !text(v.reason, 240, 3)
    || v.state !== "declared_only" || v.action !== "no_booking_or_contact") return false;
  const created = instant(v.created_at), d = v.demand, s = v.source;
  if (created === undefined || !keys(d, "institute_id customer_id service_id declared_at duration_minutes availability allowed_employee_ids constraints_review availability_evidence constraints_evidence")
    || !keys(s, "customer_id registered_at service_id duration_minutes allowed_employee_ids") || d.institute_id !== institute
    || !id(d.customer_id) || !id(d.service_id) || instant(d.declared_at) !== created || !count(d.duration_minutes)
    || d.duration_minutes < 1 || d.duration_minutes > 1440 || !ids(d.allowed_employee_ids)
    || !text(d.availability_evidence, 240, 3) || !["confirmed", "unknown"].includes(String(d.constraints_review))
    || (d.constraints_review === "confirmed" ? !text(d.constraints_evidence, 240, 3) : d.constraints_evidence !== null)
    || !Array.isArray(d.availability) || d.availability.length < 1 || d.availability.length > 64) return false;
  let previous: bigint | undefined;
  for (const window of d.availability) {
    if (!keys(window, "start end")) return false;
    const start = instant(window.start), end = instant(window.end);
    if (start === undefined || end === undefined || start >= end || end <= created || previous !== undefined && start < previous) return false;
    previous = end;
  }
  const registered = instant(s.registered_at);
  const declaredEmployees = d.allowed_employee_ids;
  return registered !== undefined && registered <= created && s.customer_id === d.customer_id && s.service_id === d.service_id
    && s.duration_minutes === d.duration_minutes && ids(s.allowed_employee_ids)
    && s.allowed_employee_ids.length === declaredEmployees.length
    && s.allowed_employee_ids.every((value, index) => value === declaredEmployees[index]);
}

export async function validWaitlistEnvelope(v: unknown, institute: string): Promise<boolean> {
  try {
    return keys(v, "original fingerprint") && typeof v.fingerprint === "string" && /^[0-9a-f]{64}$/.test(v.fingerprint)
      && validWaitlistOriginalShape(v.original, institute) && await revenueOriginalFingerprint(v.original) === v.fingerprint;
  } catch { return false; }
}

export async function validWaitlistOriginalAudit(v: unknown, institute: string, offset: number): Promise<boolean> {
  if (!count(offset) || !keys(v, "institute_id captured_at offset limit total originals basis") || v.institute_id !== institute
    || v.offset !== offset || v.limit !== 20 || !count(v.total) || v.basis !== "verified_retained_declarations_not_active_waitlist"
    || !Array.isArray(v.originals) || v.originals.length !== Math.min(20, Math.max(0, v.total-offset))) return false;
  const captured = instant(v.captured_at);
  if (captured === undefined) return false;
  const seen = new Set<string>(); let previous: WaitlistOriginal | undefined;
  for (const envelope of v.originals) {
    if (!await validWaitlistEnvelope(envelope, institute)) return false;
    const original = (envelope as WaitlistEnvelope).original;
    const created = instant(original.created_at)!;
    if (created > captured || seen.has(original.id) || previous && (created < instant(previous.created_at)!
        || created === instant(previous.created_at)! && original.id <= previous.id)) return false;
    seen.add(original.id); previous = original;
  }
  return true;
}
