import { certificationInstant as instant } from "./certification-utils";
import { revenueOriginalFingerprint } from "./revenue-scenario-utils";
import { validLifecycleOriginal, type LifecycleOriginal } from "./crm-lifecycle-utils";
import { validWaitlistLifecycleState, type WaitlistLifecycleState } from "./waitlist-lifecycle-utils";
import type { WaitlistOriginal } from "./waitlist-original-utils";

export type WaitlistPolicy = { channel: "email" | "sms"; history_requirement: "review_only" | "observed_care_required" | "no_recorded_care_required";
  permission_requirement: "review_only" | "recorded_grant_required" };
type Window = { start: string; end: string };
type Need = { kind: string; capability: string; quantity: number };
type Employee = { employee_id: string; skills: string[]; state: "known" | "unknown"; windows: Window[] };
type Resource = { resource_id: string; kind: string; capabilities: string[]; state: "active_known" | "inactive" | "unknown"; reservations: Window[] };
type Context = { customer_id: string; history: "observed" | "no_recorded_care" | "unknown"; history_reference: string | null; history_at: string | null;
  permission: "granted" | "refused" | "unknown"; channel: "email" | "sms"; purpose: "service_follow_up"; permission_at: string | null; permission_reference: string | null };
type Capture = { institute_id: string; captured_at: string; service: { service_id: string; duration_minutes: number; required_skills: string[]; needs: Need[]; resource_configuration: "known" | "unknown" };
  employees: Employee[]; resources: Resource[]; customer: Context; customer_capacity: "known" | "unknown"; customer_blockers: Window[]; queue_capacity: "known" | "unknown" };
type Option = Window & { employee_id: string; resource_ids: string[] };
export type WaitlistReview = { demand: WaitlistOriginal["demand"]; capture: Capture; options: Option[]; unavailable_reason: string | null;
  confidence: "conditional_recorded_capacity"; action: "manual_review_only" };
type Care = { ticket_id: string; started_at: string; completed_at: string; execution_count: number; service_ids: string[] };
type QueueSlot = Window & { ticket_id: string; employee_id: string; resource_ids: string[] };
export type WaitlistMatchingEvidence = { registered_at: string; latest_care: Care | null; observed_care_episodes: number; care_diagnostics: Record<string, number>;
  permission_original: LifecycleOriginal | null; permission_reason: "declaration_absent" | "future_declaration" | "current_declaration";
  employee_reasons: Record<string, string>; customer_booking_ids: string[]; customer_session_ids: string[]; waiting_tickets: number; queue_slots: QueueSlot[]; unprojectable_queue_tickets: number;
  capacity_basis: "recorded_employee_bookings_sessions_absences_and_resource_reservations"; queue_basis: "existing_core_queue_allocations_as_virtual_blockers_not_reservations";
  opening_hours: "not_verified"; contact_authority: "not_granted_by_this_read"; history_coverage: "recorded_ticket_care_since_registration_not_complete_real_history" };
export type WaitlistMatching = { state: WaitlistLifecycleState; captured_at: string; horizon_end: string; policy: WaitlistPolicy; review: WaitlistReview | null;
  evidence: WaitlistMatchingEvidence | null; unavailable_reason: string | null; action: "review_then_revalidate_before_booking_or_contact" };
export type WaitlistMatchingSelection = { state: WaitlistLifecycleState; horizon_end: string; policy: WaitlistPolicy };
export type WaitlistDetection = { institute_id: string; captured_at: string; horizon_end: string; policy: WaitlistPolicy; offset: number; limit: number;
  examined_roots: number; active: number; cancelled: number; with_options: number; without_options: number; unavailable_reasons: Record<string, number>; reviews: WaitlistMatching[];
  basis: "whole_active_cohort_verified_before_paging"; allocation: "independent_alternatives_not_jointly_reserved"; action: "no_booking_or_contact" };
const keys = (v: unknown, names: string): v is Record<string, any> => !!v && typeof v === "object" && !Array.isArray(v)
  && Object.keys(v).sort().join(" ") === names.split(" ").sort().join(" ");
const id = (v: unknown): v is string => typeof v === "string" && !!v && v.trim() === v && Array.from(v).length <= 80 && !/[\x00-\x1f]/.test(v);
const count = (v: unknown): v is number => typeof v === "number" && Number.isSafeInteger(v) && v >= 0;
const ids = (v: unknown): v is string[] => Array.isArray(v) && v.every(id) && new Set(v).size === v.length;
const one = (v: unknown, values: string) => typeof v === "string" && values.split(" ").includes(v);
const window = (v: unknown): v is Window => keys(v, "start end") && instant(v.start) !== undefined && instant(v.end) !== undefined && instant(v.start)! < instant(v.end)!;
const windows = (v: unknown, ordered = false): v is Window[] => Array.isArray(v) && v.every(window)
  && (!ordered || v.every((w, n) => !n || instant(v[n - 1].end)! <= instant(w.start)!));
const overlaps = (a: Window, b: Window) => instant(a.start)! < instant(b.end)! && instant(b.start)! < instant(a.end)!;
const contains = (a: Window, b: Window) => instant(a.start)! <= instant(b.start)! && instant(b.end)! <= instant(a.end)!;
const sameTime = (a: unknown, b: unknown) => instant(a) !== undefined && instant(a) === instant(b);
const reviewReasons = "constraints_unknown duration_changed resource_configuration_unknown customer_capacity_unknown queue_projection_unknown no_matching_recorded_capacity";
const readReasons = "cancelled registration_unavailable active_service_unavailable history_requirement_unmet permission_requirement_unmet";
function compare(a: string, b: string) {
  const left = Array.from(a, c => c.codePointAt(0)!), right = Array.from(b, c => c.codePointAt(0)!);
  for (let n = 0; n < Math.min(left.length, right.length); n++) if (left[n] !== right[n]) return left[n] - right[n];
  return left.length - right.length;
}
export function validWaitlistPolicy(v: unknown): v is WaitlistPolicy {
  return keys(v, "channel history_requirement permission_requirement") && one(v.channel, "email sms")
    && one(v.history_requirement, "review_only observed_care_required no_recorded_care_required") && one(v.permission_requirement, "review_only recorded_grant_required");
}
function validEvidence(v: unknown, state: WaitlistLifecycleState, clock: bigint): v is WaitlistMatchingEvidence {
  if (!keys(v, "registered_at latest_care observed_care_episodes care_diagnostics permission_original permission_reason employee_reasons customer_booking_ids customer_session_ids waiting_tickets queue_slots unprojectable_queue_tickets capacity_basis queue_basis opening_hours contact_authority history_coverage")
    || instant(v.registered_at) === undefined || instant(v.registered_at)! > clock || !count(v.observed_care_episodes)
    || !keys(v.care_diagnostics, "unlinked_ticket invalid_owner_or_service invalid_actual_times") || !Object.values(v.care_diagnostics).every(count)
    || !ids(v.customer_booking_ids) || !ids(v.customer_session_ids) || !count(v.waiting_tickets) || !count(v.unprojectable_queue_tickets)
    || !Array.isArray(v.queue_slots) || !v.queue_slots.every((s: any) => keys(s, "ticket_id employee_id start end resource_ids") && id(s.ticket_id) && id(s.employee_id)
      && window({ start: s.start, end: s.end }) && instant(s.start)! >= clock && ids(s.resource_ids))
    || new Set(v.queue_slots.map((s: QueueSlot) => s.ticket_id)).size !== v.queue_slots.length
    || BigInt(v.queue_slots.length) + BigInt(v.unprojectable_queue_tickets) !== BigInt(v.waiting_tickets)
    || !v.employee_reasons || typeof v.employee_reasons !== "object" || Array.isArray(v.employee_reasons)
    || !Object.entries(v.employee_reasons).every(([k, r]) => id(k) && typeof r === "string" && !!r)
    || v.capacity_basis !== "recorded_employee_bookings_sessions_absences_and_resource_reservations"
    || v.queue_basis !== "existing_core_queue_allocations_as_virtual_blockers_not_reservations" || v.opening_hours !== "not_verified"
    || v.contact_authority !== "not_granted_by_this_read" || v.history_coverage !== "recorded_ticket_care_since_registration_not_complete_real_history") return false;
  const care = v.latest_care;
  if (care !== null && (!keys(care, "ticket_id started_at completed_at execution_count service_ids") || !id(care.ticket_id)
    || !window({ start: care.started_at, end: care.completed_at }) || instant(care.completed_at)! >= clock || instant(care.completed_at)! < instant(v.registered_at)!
    || !count(care.execution_count) || !care.execution_count || !ids(care.service_ids) || !care.service_ids.length || !v.observed_care_episodes
    || Object.values(v.care_diagnostics).some(n => n !== 0))) return false;
  if (care === null && v.observed_care_episodes > 0 && Object.values(v.care_diagnostics).every(n => n === 0) && instant(v.registered_at)! < clock) return false;
  const permission = v.permission_original;
  if (permission === null) return v.permission_reason === "declaration_absent";
  if (!keys(permission, "declaration previous_id reason idempotency_key id institute_id customer_id actor_id created_at")
    || !validLifecycleOriginal(permission, state.root.original.institute_id, state.root.original.demand.customer_id)
    || !keys(permission.declaration, "institute_id customer_id birthday birthday_evidence communications")
    || !permission.declaration.communications.every(c => keys(c, "channel purpose permission evidence"))) return false;
  return v.permission_reason === (instant(permission.created_at)! > clock ? "future_declaration" : "current_declaration");
}
function validCapture(v: unknown, institute: string, clock: bigint, horizon: bigint): v is Capture {
  if (!keys(v, "institute_id captured_at service employees resources customer customer_capacity customer_blockers queue_capacity") || v.institute_id !== institute || instant(v.captured_at) !== clock
    || !keys(v.service, "service_id duration_minutes required_skills needs resource_configuration") || !id(v.service.service_id) || !count(v.service.duration_minutes)
    || v.service.duration_minutes < 1 || v.service.duration_minutes > 1440 || !ids(v.service.required_skills) || !one(v.service.resource_configuration, "known unknown")
    || !Array.isArray(v.service.needs) || !v.service.needs.every((n: any) => keys(n, "kind capability quantity") && one(n.kind, "room equipment bed chair device")
      && typeof n.capability === "string" && count(n.quantity) && n.quantity >= 1 && n.quantity <= 10)
    || new Set(v.service.needs.map((n: Need) => JSON.stringify([n.kind, n.capability]))).size !== v.service.needs.length
    || !Array.isArray(v.employees) || !v.employees.every((e: any) => keys(e, "employee_id skills state windows") && id(e.employee_id) && ids(e.skills)
      && one(e.state, "known unknown") && windows(e.windows, true) && (e.state !== "unknown" || !e.windows.length)
      && e.windows.every((w: Window) => instant(w.start)! >= clock && instant(w.end)! <= horizon))
    || new Set(v.employees.map((e: Employee) => e.employee_id)).size !== v.employees.length
    || !Array.isArray(v.resources) || !v.resources.every((r: any) => keys(r, "resource_id kind capabilities state reservations") && id(r.resource_id)
      && one(r.kind, "room equipment bed chair device") && Array.isArray(r.capabilities) && r.capabilities.every((c: unknown) => typeof c === "string")
      && one(r.state, "active_known inactive unknown") && windows(r.reservations))
    || new Set(v.resources.map((r: Resource) => r.resource_id)).size !== v.resources.length
    || !one(v.customer_capacity, "known unknown") || !one(v.queue_capacity, "known unknown") || !windows(v.customer_blockers)) return false;
  const c = v.customer;
  return keys(c, "customer_id history history_reference history_at permission channel purpose permission_at permission_reference") && id(c.customer_id)
    && one(c.history, "observed no_recorded_care unknown") && one(c.permission, "granted refused unknown") && one(c.channel, "email sms") && c.purpose === "service_follow_up"
    && (c.history === "observed" ? id(c.history_reference) && instant(c.history_at) !== undefined && instant(c.history_at)! <= clock : c.history_reference === null && c.history_at === null)
    && (c.permission === "unknown" ? c.permission_reference === null && c.permission_at === null : id(c.permission_reference) && instant(c.permission_at) !== undefined && instant(c.permission_at)! <= clock);
}
// Verify the displayed distinct units cover the captured needs. This does not find
// alternative capacity or replace the sovereign backend matching calculation.
function covers(resources: Resource[], needs: Need[]) {
  const units = needs.flatMap(n => Array.from({ length: n.quantity }, () => n));
  if (units.length !== resources.length) return false;
  const assigned = new Map<number, number>();
  const visit = (u: number, seen: Set<number>): boolean => resources.some((r, n) => {
    if (seen.has(n) || r.kind !== units[u].kind || !r.capabilities.includes(units[u].capability)) return false;
    seen.add(n); const prior = assigned.get(n);
    if (prior !== undefined && !visit(prior, seen)) return false;
    assigned.set(n, u); return true;
  });
  return units.every((_, n) => visit(n, new Set()));
}
function validOptions(review: WaitlistReview, clock: bigint, horizon: bigint) {
  const { demand, capture, options } = review;
  if (!Array.isArray(options) || (review.unavailable_reason === null ? !options.length : options.length !== 0)) return false;
  if (options.length && (demand.constraints_review !== "confirmed" || demand.duration_minutes !== capture.service.duration_minutes
    || capture.service.resource_configuration !== "known" || capture.customer_capacity !== "known" || capture.queue_capacity !== "known")) return false;
  const identities = new Set<string>(); let previous: Option | undefined;
  for (const o of options) {
    if (!keys(o, "employee_id start end resource_ids") || !id(o.employee_id) || !window({ start: o.start, end: o.end }) || !ids(o.resource_ids)
      || instant(o.start)! < clock || instant(o.end)! > horizon || instant(o.end)! - instant(o.start)! !== BigInt(demand.duration_minutes) * 60_000_000n) return false;
    const identity = JSON.stringify([String(instant(o.start)), String(instant(o.end)), o.employee_id, [...o.resource_ids].sort(compare)]);
    if (identities.has(identity) || previous && (instant(previous.start)! > instant(o.start)! || sameTime(previous.start, o.start) && compare(previous.employee_id, o.employee_id) > 0)) return false;
    identities.add(identity); previous = o;
    const employee = capture.employees.find(e => e.employee_id === o.employee_id);
    const resources = o.resource_ids.map(id => capture.resources.find(r => r.resource_id === id));
    if (!employee || employee.state !== "known" || demand.allowed_employee_ids.length && !demand.allowed_employee_ids.includes(o.employee_id)
      || !capture.service.required_skills.every(s => employee.skills.includes(s)) || !employee.windows.some(w => contains(w, o))
      || !demand.availability.some(w => contains(w, o)) || capture.customer_blockers.some(w => overlaps(w, o))
      || resources.some(r => !r || r.state !== "active_known" || r.reservations.some(w => overlaps(w, o))) || !covers(resources as Resource[], capture.service.needs)) return false;
  }
  return true;
}
export async function validWaitlistMatching(v: unknown, institute: string, selection: WaitlistMatchingSelection): Promise<boolean> {
  try {
    if (!keys(v, "state captured_at horizon_end policy review evidence unavailable_reason action") || !validWaitlistPolicy(selection.policy)
      || !validWaitlistPolicy(v.policy) || Object.keys(selection.policy).some(k => v.policy[k] !== selection.policy[k as keyof WaitlistPolicy])
      || !sameTime(v.horizon_end, selection.horizon_end) || v.action !== "review_then_revalidate_before_booking_or_contact"
      || !await validWaitlistLifecycleState(selection.state, institute) || !await validWaitlistLifecycleState(v.state, institute)) return false;
    const clock = instant(v.captured_at), horizon = instant(v.horizon_end);
    if (clock === undefined || horizon === undefined || clock >= horizon || v.state.root.fingerprint !== selection.state.root.fingerprint
      || v.state.events.length !== selection.state.events.length || v.state.events.some((e: any, n: number) => e.original.id !== selection.state.events[n].original.id
        || e.fingerprint !== selection.state.events[n].fingerprint || instant(e.original.created_at)! > clock)) return false;
    if (v.unavailable_reason !== null && !one(v.unavailable_reason, readReasons)) return false;
    if (one(v.unavailable_reason, "cancelled registration_unavailable active_service_unavailable")) return v.review === null && v.evidence === null
      && (v.unavailable_reason === "cancelled" ? v.state.state === "cancelled" : v.state.state === "active");
    if (v.state.state !== "active" || !validEvidence(v.evidence, v.state, clock)) return false;
    const e = v.evidence;
    const expectedHistory = instant(e.registered_at)! === clock || Object.values(e.care_diagnostics).some(n => n !== 0) ? "unknown" : e.latest_care ? "observed" : "no_recorded_care";
    const permission = e.permission_reason === "current_declaration" ? e.permission_original!.declaration.communications.find(x => x.channel === v.policy.channel && x.purpose === "service_follow_up")! : null;
    const policyReason = v.policy.history_requirement === "observed_care_required" && expectedHistory !== "observed"
      || v.policy.history_requirement === "no_recorded_care_required" && expectedHistory !== "no_recorded_care" ? "history_requirement_unmet"
      : v.policy.permission_requirement === "recorded_grant_required" && permission?.permission !== "granted" ? "permission_requirement_unmet" : null;
    if (v.unavailable_reason !== policyReason) return false;
    if (v.review === null) return policyReason !== null;
    const r = v.review;
    if (v.unavailable_reason !== null || !keys(r, "demand capture options unavailable_reason confidence action") || r.confidence !== "conditional_recorded_capacity"
      || r.action !== "manual_review_only" || r.unavailable_reason !== null && !one(r.unavailable_reason, reviewReasons)
      || await revenueOriginalFingerprint(r.demand) !== await revenueOriginalFingerprint(v.state.current_demand.original.demand)
      || !validCapture(r.capture, institute, clock, horizon) || r.capture.service.service_id !== r.demand.service_id || r.capture.customer.customer_id !== r.demand.customer_id
      || Object.keys(e.employee_reasons).sort().join(" ") !== r.capture.employees.map((x: Employee) => x.employee_id).sort().join(" ")
      || r.capture.queue_capacity !== (e.unprojectable_queue_tickets ? "unknown" : "known")) return false;
    const c = r.capture.customer;
    if (c.history !== expectedHistory || c.channel !== v.policy.channel || c.permission !== (permission?.permission ?? "unknown")
      || c.history === "observed" && (c.history_reference !== e.latest_care!.ticket_id || !sameTime(c.history_at, e.latest_care!.completed_at))
      || c.permission !== "unknown" && (c.permission_reference !== e.permission_original!.id || !sameTime(c.permission_at, e.permission_original!.created_at))
      || v.policy.history_requirement === "observed_care_required" && c.history !== "observed"
      || v.policy.history_requirement === "no_recorded_care_required" && c.history !== "no_recorded_care"
      || v.policy.permission_requirement === "recorded_grant_required" && c.permission !== "granted") return false;
    // Projected employee/resource blockers must remain visible in captured capacity.
    for (const slot of e.queue_slots) {
      if (!r.capture.employees.some(x => x.employee_id === slot.employee_id) || r.capture.employees.find(x => x.employee_id === slot.employee_id)!.windows.some(w => overlaps(w, slot))) return false;
      for (const id of slot.resource_ids) if (!r.capture.resources.find(x => x.resource_id === id)?.reservations.some(w => sameTime(w.start, slot.start) && sameTime(w.end, slot.end))) return false;
    }
    const reason = r.demand.constraints_review !== "confirmed" ? "constraints_unknown" : r.demand.duration_minutes !== r.capture.service.duration_minutes ? "duration_changed"
      : r.capture.service.resource_configuration !== "known" ? "resource_configuration_unknown" : r.capture.customer_capacity !== "known" ? "customer_capacity_unknown"
      : r.capture.queue_capacity !== "known" ? "queue_projection_unknown" : Array.isArray(r.options) && !r.options.length ? "no_matching_recorded_capacity" : null;
    return r.unavailable_reason === reason && validOptions(r as WaitlistReview, clock, horizon);
  } catch { return false; }
}
export async function validWaitlistDetection(v: unknown, institute: string, horizon: string, policy: WaitlistPolicy, offset: number): Promise<boolean> {
  try {
    if (!keys(v, "institute_id captured_at horizon_end policy offset limit examined_roots active cancelled with_options without_options unavailable_reasons reviews basis allocation action")
      || v.institute_id !== institute || !sameTime(v.horizon_end, horizon) || !validWaitlistPolicy(policy) || !validWaitlistPolicy(v.policy)
      || Object.keys(policy).some(k => policy[k as keyof WaitlistPolicy] !== v.policy[k]) || !count(offset) || v.offset !== offset || v.limit !== 20
      || ![v.examined_roots, v.active, v.cancelled, v.with_options, v.without_options].every(count)
      || BigInt(v.active) + BigInt(v.cancelled) !== BigInt(v.examined_roots) || BigInt(v.with_options) + BigInt(v.without_options) !== BigInt(v.active)
      || v.basis !== "whole_active_cohort_verified_before_paging" || v.allocation !== "independent_alternatives_not_jointly_reserved" || v.action !== "no_booking_or_contact"
      || !v.unavailable_reasons || typeof v.unavailable_reasons !== "object" || Array.isArray(v.unavailable_reasons)
      || !Object.entries(v.unavailable_reasons).every(([reason, n]) => reason !== "cancelled" && one(reason, `${readReasons} ${reviewReasons}`) && count(n) && n > 0)
      || Object.values(v.unavailable_reasons).reduce<bigint>((sum, n) => sum + BigInt(n as number), 0n) !== BigInt(v.without_options)
      || !Array.isArray(v.reviews) || v.reviews.length !== Math.min(20, Math.max(0, v.active - offset))) return false;
    const clock = instant(v.captured_at), end = instant(v.horizon_end);
    if (clock === undefined || end === undefined || clock >= end) return false;
    const roots = new Set<string>(), events = new Set<string>(), keysSeen = new Set<string>(), reasons: Record<string, number> = {}; let withOptions = 0, prior: string | undefined;
    for (const r of v.reviews as WaitlistMatching[]) {
      if (!r || !sameTime(r.captured_at, v.captured_at) || !await validWaitlistMatching(r, institute, { state: r.state, horizon_end: horizon, policy }) || r.state.state !== "active") return false;
      const root = r.state.root.original.id;
      if (roots.has(root) || prior !== undefined && compare(prior, root) >= 0) return false;
      roots.add(root); prior = root;
      for (const e of r.state.events) {
        if (events.has(e.original.id) || keysSeen.has(e.original.idempotency_key)) return false;
        events.add(e.original.id); keysSeen.add(e.original.idempotency_key);
      }
      if (r.review?.options.length) withOptions++;
      else { const reason = r.unavailable_reason ?? r.review?.unavailable_reason; if (!reason) return false; reasons[reason] = (reasons[reason] ?? 0) + 1; }
    }
    if (withOptions > v.with_options || v.reviews.length - withOptions > v.without_options || Object.entries(reasons).some(([reason, n]) => n > (v.unavailable_reasons[reason] ?? 0))) return false;
    return offset !== 0 || v.reviews.length !== v.active || withOptions === v.with_options && Object.entries(v.unavailable_reasons).every(([reason, n]) => reasons[reason] === n);
  } catch { return false; }
}
