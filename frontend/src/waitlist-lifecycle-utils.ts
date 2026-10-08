import { certificationInstant as instant } from "./certification-utils";
import { revenueOriginalFingerprint } from "./revenue-scenario-utils";
import { validWaitlistEnvelope, type WaitlistEnvelope, type WaitlistOriginal } from "./waitlist-original-utils";

export type WaitlistLifecycleRequest = { root_id: string; root_fingerprint: string; previous_id: string | null; previous_fingerprint: string | null;
  action: "activate" | "revise" | "cancel"; target_id: string; target_fingerprint: string; reason: string; idempotency_key: string };
export type WaitlistLifecycleEvent = WaitlistLifecycleRequest & { id: string; institute_id: string; actor_id: string; created_at: string;
  activation_source: WaitlistOriginal["source"] | null; effect: "waitlist_state_only_no_booking_or_contact" };
export type WaitlistLifecycleEnvelope = { original: WaitlistLifecycleEvent; fingerprint: string };
export type WaitlistLifecycleState = { root: WaitlistEnvelope; current_demand: WaitlistEnvelope; state: "active" | "cancelled"; events: WaitlistLifecycleEnvelope[] };
export type WaitlistLifecycleAudit = { institute_id: string; captured_at: string; offset: number; limit: number; total: number;
  active: number; cancelled: number; states: WaitlistLifecycleState[] };
const keys = (v: unknown, names: string): v is Record<string, unknown> => !!v && typeof v === "object" && !Array.isArray(v)
  && Object.keys(v).sort().join(" ") === names.split(" ").sort().join(" ");
const text = (v: unknown, max: number, min = 1): v is string => typeof v === "string" && v.trim() === v && Array.from(v).length >= min && Array.from(v).length <= max;
const identity = (v: unknown, max = 80): v is string => text(v, max) && !/[\x00-\x1f]/.test(v);
const fingerprint = (v: unknown): v is string => typeof v === "string" && /^[0-9a-f]{64}$/.test(v);
const count = (v: unknown): v is number => typeof v === "number" && Number.isSafeInteger(v) && v >= 0;
const requestKeys = "root_id root_fingerprint previous_id previous_fingerprint action target_id target_fingerprint reason idempotency_key";
function requestFields(v: Record<string, unknown>) {
  return identity(v.root_id) && identity(v.target_id) && fingerprint(v.root_fingerprint) && fingerprint(v.target_fingerprint)
    && (v.root_id !== v.target_id || v.root_fingerprint === v.target_fingerprint) && text(v.reason, 240, 3) && identity(v.idempotency_key, 120)
    && (v.action === "activate" ? v.previous_id === null && v.previous_fingerprint === null && v.root_id === v.target_id
      : (v.action === "revise" || v.action === "cancel") && identity(v.previous_id) && fingerprint(v.previous_fingerprint));
}
export function validWaitlistLifecycleRequest(v: unknown): v is WaitlistLifecycleRequest { return keys(v, requestKeys) && requestFields(v); }
function validSource(v: unknown, capture: bigint): v is WaitlistOriginal["source"] {
  if (!keys(v, "customer_id registered_at service_id duration_minutes allowed_employee_ids") || !identity(v.customer_id) || !identity(v.service_id)
    || !count(v.duration_minutes) || v.duration_minutes < 1 || v.duration_minutes > 1440 || !Array.isArray(v.allowed_employee_ids)
    || v.allowed_employee_ids.length > 100 || !v.allowed_employee_ids.every(id => identity(id)) || new Set(v.allowed_employee_ids).size !== v.allowed_employee_ids.length) return false;
  const registered = instant(v.registered_at); return registered !== undefined && registered <= capture;
}
export async function validWaitlistLifecycleEnvelope(v: unknown, institute: string): Promise<boolean> {
  try {
    if (!keys(v, "original fingerprint") || !fingerprint(v.fingerprint)
      || !keys(v.original, `${requestKeys} id institute_id actor_id created_at activation_source effect`)) return false;
    const e = v.original, capture = instant(e.created_at);
    return requestFields(e) && identity(e.id) && e.institute_id === institute && identity(e.actor_id, 160) && capture !== undefined
      && e.id !== e.previous_id && e.effect === "waitlist_state_only_no_booking_or_contact"
      && (e.action === "cancel" ? e.activation_source === null : validSource(e.activation_source, capture))
      && await revenueOriginalFingerprint(e) === v.fingerprint;
  } catch { return false; }
}
function sameEnvelope(a: { original: { id: string }; fingerprint: string }, b: { original: { id: string }; fingerprint: string }) {
  return a.original.id === b.original.id && a.fingerprint === b.fingerprint;
}
export function waitlistLifecycleBindsTarget(event: WaitlistLifecycleEvent, target: WaitlistEnvelope) {
  const capture = instant(event.created_at)!, original = target.original, demand = original.demand;
  if (instant(original.created_at)! > capture) return false;
  if (event.action === "cancel") return true;
  const source = event.activation_source!;
  return source.customer_id === demand.customer_id && source.service_id === demand.service_id && source.duration_minutes === demand.duration_minutes
    && source.allowed_employee_ids.length === demand.allowed_employee_ids.length && source.allowed_employee_ids.every((id, n) => id === demand.allowed_employee_ids[n])
    && demand.availability.some(w => instant(w.end)! > capture);
}
export async function validWaitlistLifecycleState(v: unknown, institute: string): Promise<boolean> {
  if (!keys(v, "root current_demand state events") || !["active", "cancelled"].includes(String(v.state))
    || !await validWaitlistEnvelope(v.root, institute) || !await validWaitlistEnvelope(v.current_demand, institute)
    || !Array.isArray(v.events) || v.events.length < 1) return false;
  const root = v.root as WaitlistEnvelope, current = v.current_demand as WaitlistEnvelope;
  if (root.original.demand.customer_id !== current.original.demand.customer_id) return false;
  if (root.original.id === current.original.id && !sameEnvelope(root, current)) return false;
  const seen = new Set<string>(), seenKeys = new Set<string>(); let previous: WaitlistLifecycleEnvelope | undefined;
  let targetId = root.original.id, targetFingerprint = root.fingerprint, cancelled = false;
  for (const value of v.events) {
    if (!await validWaitlistLifecycleEnvelope(value, institute)) return false;
    const envelope = value as WaitlistLifecycleEnvelope, event = envelope.original;
    const capture = instant(event.created_at)!;
    if (cancelled || seen.has(event.id) || seenKeys.has(event.idempotency_key) || event.root_id !== root.original.id || event.root_fingerprint !== root.fingerprint
      || capture < instant(root.original.created_at)! || event.activation_source && event.activation_source.customer_id !== root.original.demand.customer_id) return false;
    if (!previous) {
      if (event.action !== "activate" || event.target_id !== targetId || event.target_fingerprint !== targetFingerprint) return false;
    } else if (event.action === "activate" || event.previous_id !== previous.original.id || event.previous_fingerprint !== previous.fingerprint
      || capture < instant(previous.original.created_at)!) return false;
    if (event.action === "cancel" && (event.target_id !== targetId || event.target_fingerprint !== targetFingerprint)
      || event.action === "revise" && event.target_id === targetId) return false;
    // State returns root/current originals; intermediate replacement declarations
    // stay opaque references. Backend verifies those omitted original source rows.
    for (const target of [root, current]) {
      if (event.target_id === target.original.id && (event.target_fingerprint !== target.fingerprint || !waitlistLifecycleBindsTarget(event, target))) return false;
    }
    targetId = event.target_id; targetFingerprint = event.target_fingerprint; cancelled = event.action === "cancel";
    seen.add(event.id); seenKeys.add(event.idempotency_key); previous = envelope;
  }
  return targetId === current.original.id && targetFingerprint === current.fingerprint && v.state === (cancelled ? "cancelled" : "active");
}
export async function validWaitlistLifecycleAudit(v: unknown, institute: string, offset: number): Promise<boolean> {
  if (!count(offset) || !keys(v, "institute_id captured_at offset limit total active cancelled states") || v.institute_id !== institute || v.offset !== offset
    || v.limit !== 20 || !count(v.total) || !count(v.active) || !count(v.cancelled) || BigInt(v.active)+BigInt(v.cancelled) !== BigInt(v.total)
    || !Array.isArray(v.states) || v.states.length !== Math.min(20, Math.max(0, v.total-offset))) return false;
  const capture = instant(v.captured_at); if (capture === undefined) return false;
  let previous = "", active = 0, cancelled = 0; const eventIds = new Set<string>(), eventKeys = new Set<string>();
  for (const value of v.states) {
    if (!await validWaitlistLifecycleState(value, institute)) return false;
    const state = value as WaitlistLifecycleState, id = state.root.original.id;
    if (previous && id <= previous || instant(state.root.original.created_at)! > capture || instant(state.current_demand.original.created_at)! > capture) return false;
    for (const event of state.events) {
      if (instant(event.original.created_at)! > capture || eventIds.has(event.original.id) || eventKeys.has(event.original.idempotency_key)) return false;
      eventIds.add(event.original.id); eventKeys.add(event.original.idempotency_key);
    }
    previous = id; if (state.state === "active") active++; else cancelled++;
  }
  return active <= v.active && cancelled <= v.cancelled && (offset !== 0 || v.total !== v.states.length || active === v.active && cancelled === v.cancelled);
}
