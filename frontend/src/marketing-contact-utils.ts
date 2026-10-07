import { certificationInstant as instant } from "./certification-utils";

export type ContactChannel = "email" | "sms" | "push";
export type ContactDestination = { channel: ContactChannel; email: string | null; phone: string | null;
  push_application: string | null; push_token: string | null; evidence: string };
export type ContactCommunication = { channel: ContactChannel; purpose?: never; permission: "unknown" | "granted" | "refused";
  permission_evidence: string | null; destination: ContactDestination | null };
export type ContactDeclaration = { institute_id: string; customer_id: string; purpose: "marketing"; communications: ContactCommunication[] };
export type ContactRequest = { declaration: ContactDeclaration; previous_id: string | null; reason: string; idempotency_key: string };
export type ContactOriginal = ContactRequest & { id: string; actor_id: string; created_at: string };
const keys = (v: unknown, names: string[]) => !!v && typeof v === "object" && !Array.isArray(v)
  && Object.keys(v).length === names.length && names.every(k => Object.prototype.hasOwnProperty.call(v, k));
const text = (v: unknown, max: number): v is string => typeof v === "string" && !!v.trim() && v.trim() === v && Array.from(v).length <= max;
const evidence = (v: unknown): v is string => text(v, 240) && Array.from(v).length >= 3;
const channels = ["email", "sms", "push"];
function validDestination(v: unknown, channel: ContactChannel): v is ContactDestination {
  const d = v as ContactDestination;
  if (!keys(d, ["channel", "email", "phone", "push_application", "push_token", "evidence"]) || d.channel !== channel || !evidence(d.evidence)) return false;
  if (channel === "email") return typeof d.email === "string" && /^[^\s@]+@[^\s@]+$/u.test(d.email) && !/[\x00-\x1f\x7f]/.test(d.email)
    && d.phone === null && d.push_application === null && d.push_token === null;
  if (channel === "sms") return text(d.phone, 16) && /^\+[1-9][0-9]{1,14}$/.test(d.phone)
    && d.email === null && d.push_application === null && d.push_token === null;
  return d.email === null && d.phone === null && text(d.push_application, 160) && text(d.push_token, 4096) && !/[\x00-\x1f\x7f]/.test(d.push_token);
}
export function validContactDeclaration(v: unknown, institute: string, customer: string): v is ContactDeclaration {
  const d = v as ContactDeclaration;
  return keys(d, ["institute_id", "customer_id", "purpose", "communications"]) && d.institute_id === institute && d.customer_id === customer
    && text(d.institute_id, 80) && text(d.customer_id, 80) && d.purpose === "marketing" && Array.isArray(d.communications)
    && d.communications.length === 3 && new Set(d.communications.map(c => c?.channel)).size === 3
    && d.communications.every(c => keys(c, ["channel", "permission", "permission_evidence", "destination"]) && channels.includes(c.channel)
      && ["unknown", "granted", "refused"].includes(c.permission)
      && (c.permission === "unknown" ? c.permission_evidence === null : evidence(c.permission_evidence))
      && (c.destination === null || validDestination(c.destination, c.channel)));
}
export function validContactRequest(v: unknown, institute: string, customer: string): v is ContactRequest {
  const r = v as ContactRequest;
  return keys(r, ["declaration", "previous_id", "reason", "idempotency_key"]) && validTerms(r, institute, customer);
}
function validTerms(r: ContactRequest, institute: string, customer: string) {
  return validContactDeclaration(r.declaration, institute, customer) && (r.previous_id === null || text(r.previous_id, 80))
    && evidence(r.reason) && text(r.idempotency_key, 120);
}
export function validContactOriginal(v: unknown, institute: string, customer: string): v is ContactOriginal {
  const r = v as ContactOriginal;
  return keys(r, ["declaration", "previous_id", "reason", "idempotency_key", "id", "actor_id", "created_at"])
    && validTerms(r, institute, customer) && text(r.id, 80) && r.previous_id !== r.id && text(r.actor_id, 160) && instant(r.created_at) !== undefined;
}
const canonical = (v: unknown): unknown => Array.isArray(v) ? v.map(canonical) : v !== null && typeof v === "object"
  ? Object.fromEntries(Object.entries(v).sort(([a], [b]) => a.localeCompare(b)).map(([k, value]) => [k, canonical(value)])) : v;
export function matchesContactReceipt(r: ContactOriginal, request: ContactRequest, actor: string): boolean {
  return r.actor_id === actor && sameContactRequest({ declaration: r.declaration, previous_id: r.previous_id, reason: r.reason, idempotency_key: r.idempotency_key }, request);
}
export function sameContactRequest(a: ContactRequest, b: ContactRequest): boolean {
  return JSON.stringify(canonical(a)) === JSON.stringify(canonical(b));
}
export function sameContactOriginal(a: ContactOriginal, b: ContactOriginal): boolean {
  return a.id === b.id && instant(a.created_at) === instant(b.created_at)
    && matchesContactReceipt(a, { declaration: b.declaration, previous_id: b.previous_id, reason: b.reason, idempotency_key: b.idempotency_key }, b.actor_id);
}
