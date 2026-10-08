import { certificationInstant as instant } from "./certification-utils";
import { revenueOriginalFingerprint } from "./revenue-scenario-utils";
export type BookingState = { status: "scheduled" | "confirmed" | "arrived" | "cancelled" | "no_show"; employee_id: string; service_id: string; customer_id: string | null;
  start_time: string; end_time: string; booked_start_time: string | null; booked_end_time: string | null; actual_start_time: string | null; actual_end_time: string | null; checkout_ticket_id: string | null };
export type ClosureEvidence = { institute_id: string; event_id: string; appointment_id: string; event_type: "cancelled" | "no_show"; actor_id: string | null;
  occurred_at: string; captured_at: string; before: BookingState; after: BookingState; retained_booking_price: null };
export type BookingClosures = { window: { institute_id: string; start: string; end: string; captured_at: string }; basis: "booking_closure_event_time";
  page: { offset: number; limit: number; total: number }; opportunities: { type: "review_cancelled_booking" | "review_no_show_booking"; evidence: ClosureEvidence;
    estimated_value: null; confidence: "recorded_closure_only_unpriced"; recommended_action: "review_booking_and_contact_permission_before_follow_up"; action_executed: false }[];
  cancelled_count: number; no_show_count: number; unpriced_count: number; institute_terminal_bookings_without_closure_event: number;
  cancelled_revenue: null; no_show_revenue: null; causal_loss_proven: false; complete_booking_history: false };
export type PriceTerms = { institute_id: string; appointment_id: string; event_id: string; event_type: "created" | "modified"; occurred_at: string; actor_id: string | null;
  service_id: string; duration_min: number; duration_max: number | null; currency: "CHF" | "EUR" | null; currency_settings_at: string | null; currency_settings_actor_id: string | null;
  currency_unavailable_reason: "settings_absent" | "settings_clock_missing" | "future_settings" | null;
  member_minor: string | null; member_quality: "known" | "missing" | "invalid"; passage_minor: string | null; passage_quality: "known" | "missing" | "invalid";
  basis: "catalog_reference_at_booking_service_selection"; agreed_quote: false; paid_price: false };
export type PriceReference = { terms: PriceTerms; fingerprint: string };
export type PriceReferences = { institute_id: string; appointment_id: string; captured_at: string; page: { offset: number; limit: number; total: number }; originals: PriceReference[]; legacy_service_selection_events: number };
export type ClosureDeclaration = { valuation: { reference_event_id: string; expected_fingerprint: string; closure_event_id: string; rate: "member" | "passage"; reason: string }; idempotency_key: string };
export type ClosureOriginal = { id: string; institute_id: string; appointment_id: string; idempotency_key: string; actor_id: string; created_at: string; retained: true;
  type: "review_booking_closure_reference_value"; request: ClosureDeclaration["valuation"]; reference: PriceReference; evidence: ClosureEvidence;
  estimated_value: { currency: "CHF" | "EUR"; amount_minor: string; basis: "explicit_historical_catalog_rate_scenario" } | null;
  unavailable_reason: "unknown_currency" | "missing_rate" | "invalid_rate" | null; confidence: "declared_rate_scenario_not_agreed_quote";
  recommended_action: "review_actual_agreement_eligibility_and_recovery_before_action"; causal_loss_proven: false; action_executed: false;
  reference_event: { id: string; institute_id: string; appointment_id: string; event_type: "created" | "modified"; occurred_at: string; actor_id: string | null; before: BookingState | null; after: BookingState } };
export type ClosureEnvelope = { original: ClosureOriginal; fingerprint: string };
export type ClosureAudit = { institute_id: string; captured_at: string; offset: number; limit: number; total: number; originals: ClosureEnvelope[]; full_original_cohort_verified: true; causal_loss_proven: false; action_executed: false };
const keys = (v: unknown, names: string): v is Record<string, unknown> => !!v && typeof v === "object" && !Array.isArray(v) && Object.keys(v).sort().join(" ") === names.split(" ").sort().join(" ");
const count = (v: unknown): v is number => typeof v === "number" && Number.isSafeInteger(v) && v >= 0;
const text = (v: unknown, max: number): v is string => typeof v === "string" && v.trim() === v && Array.from(v).length > 0 && Array.from(v).length <= max;
const id = (v: unknown): v is string => text(v, 80);
const actor = (v: unknown): v is string | null => v === null || typeof v === "string";
const minor = (v: unknown): v is string => typeof v === "string" && /^(0|[1-9][0-9]{0,9})$/.test(v);
const digest = (v: unknown): v is string => typeof v === "string" && /^[a-f0-9]{64}$/.test(v);
function state(v: unknown): v is BookingState {
  if (!keys(v, "status employee_id service_id customer_id start_time end_time booked_start_time booked_end_time actual_start_time actual_end_time checkout_ticket_id")
    || !["scheduled", "confirmed", "arrived", "cancelled", "no_show"].includes(v.status as string) || !id(v.employee_id) || !id(v.service_id)
    || v.customer_id !== null && !id(v.customer_id) || v.checkout_ticket_id !== null && !id(v.checkout_ticket_id)) return false;
  const start = instant(v.start_time), end = instant(v.end_time);
  return start !== undefined && end !== undefined && start < end && [v.booked_start_time, v.booked_end_time, v.actual_start_time, v.actual_end_time].every(t => t === null || instant(t) !== undefined);
}
const unexecuted = (v: BookingState) => v.actual_start_time === null && v.actual_end_time === null && v.checkout_ticket_id === null;
function sameState(a: BookingState, b: BookingState) {
  return (Object.keys(a) as (keyof BookingState)[]).filter(k => k !== "status").every(k => k.endsWith("_time")
    ? (a[k] === null && b[k] === null || instant(a[k]) === instant(b[k])) : a[k] === b[k]);
}
export function validClosureEvidence(v: unknown, institute: string, appointment?: string): v is ClosureEvidence {
  if (!keys(v, "institute_id event_id appointment_id event_type actor_id occurred_at captured_at before after retained_booking_price") || v.institute_id !== institute
    || !id(v.event_id) || !id(v.appointment_id) || appointment !== undefined && v.appointment_id !== appointment || !["cancelled", "no_show"].includes(v.event_type as string)
    || !actor(v.actor_id) || v.retained_booking_price !== null || !state(v.before) || !state(v.after)) return false;
  const at = instant(v.occurred_at), capture = instant(v.captured_at);
  return at !== undefined && capture !== undefined && at < capture && ["scheduled", "confirmed", "arrived"].includes(v.before.status)
    && v.after.status === v.event_type && sameState(v.before, v.after) && unexecuted(v.after);
}
function page(v: unknown, offset: number, length: number): v is { offset: number; limit: number; total: number } {
  return count(offset) && keys(v, "offset limit total") && v.offset === offset && v.limit === 20 && count(v.total) && length === Math.min(20, Math.max(0, v.total-offset));
}
export function validBookingClosures(v: unknown, institute: string, period: { start: string; end: string }, offset: number): v is BookingClosures {
  if (!keys(v, "window basis page opportunities cancelled_count no_show_count unpriced_count institute_terminal_bookings_without_closure_event cancelled_revenue no_show_revenue causal_loss_proven complete_booking_history")
    || !keys(v.window, "institute_id start end captured_at") || v.window.institute_id !== institute || v.basis !== "booking_closure_event_time"
    || v.cancelled_revenue !== null || v.no_show_revenue !== null || v.causal_loss_proven !== false || v.complete_booking_history !== false
    || !Array.isArray(v.opportunities) || !page(v.page, offset, v.opportunities.length) || ![v.cancelled_count, v.no_show_count, v.unpriced_count, v.institute_terminal_bookings_without_closure_event].every(count)) return false;
  const start = instant(v.window.start), end = instant(v.window.end), capture = instant(v.window.captured_at);
  if (start === undefined || end === undefined || capture === undefined || start >= end || end > capture || start !== instant(period.start) || end !== instant(period.end)
    || BigInt(v.cancelled_count as number)+BigInt(v.no_show_count as number) !== BigInt(v.page.total) || v.unpriced_count !== v.page.total) return false;
  let cancelled = 0, noShow = 0, previous: ClosureEvidence | undefined;
  const events = new Set(), appointments = new Set();
  for (const o of v.opportunities) {
    if (!keys(o, "type evidence estimated_value confidence recommended_action action_executed") || !validClosureEvidence(o.evidence, institute)
      || o.type !== (o.evidence.event_type === "cancelled" ? "review_cancelled_booking" : "review_no_show_booking") || o.estimated_value !== null
      || o.confidence !== "recorded_closure_only_unpriced" || o.recommended_action !== "review_booking_and_contact_permission_before_follow_up" || o.action_executed !== false) return false;
    const e = o.evidence, at = instant(e.occurred_at)!;
    if (instant(e.captured_at) !== capture || at < start || at >= end || events.has(e.event_id) || appointments.has(e.appointment_id)
      || previous && (instant(previous.occurred_at)! > at || instant(previous.occurred_at) === at && previous.event_id >= e.event_id)) return false;
    events.add(e.event_id); appointments.add(e.appointment_id); previous = e;
    if (e.event_type === "cancelled") cancelled++; else noShow++;
  }
  return cancelled <= (v.cancelled_count as number) && noShow <= (v.no_show_count as number);
}
export async function validPriceReference(v: unknown, institute: string, appointment: string): Promise<boolean> {
  if (!keys(v, "terms fingerprint") || !digest(v.fingerprint) || !keys(v.terms, "institute_id appointment_id event_id event_type occurred_at actor_id service_id duration_min duration_max currency currency_settings_at currency_settings_actor_id currency_unavailable_reason member_minor member_quality passage_minor passage_quality basis agreed_quote paid_price")) return false;
  const t = v.terms;
  if (t.institute_id !== institute || t.appointment_id !== appointment || !id(t.event_id) || !id(t.service_id) || !["created", "modified"].includes(t.event_type as string)
    || !actor(t.actor_id) || !actor(t.currency_settings_actor_id) || !count(t.duration_min) || t.duration_max !== null && !count(t.duration_max)
    || t.basis !== "catalog_reference_at_booking_service_selection" || t.agreed_quote !== false || t.paid_price !== false) return false;
  const at = instant(t.occurred_at), configured = t.currency_settings_at === null ? null : instant(t.currency_settings_at);
  if (at === undefined || configured === undefined) return false;
  for (const rate of ["member", "passage"]) {
    const quality = t[rate+"_quality"], amount = t[rate+"_minor"];
    if (!["known", "missing", "invalid"].includes(quality as string) || (quality === "known" ? !minor(amount) : amount !== null)) return false;
  }
  const reason = t.currency_unavailable_reason;
  if (reason === null ? !["CHF", "EUR"].includes(t.currency as string) || configured === null || configured > at
    : !["settings_absent", "settings_clock_missing", "future_settings"].includes(reason as string) || t.currency !== null
      || reason === "future_settings" && (configured === null || configured <= at) || reason !== "future_settings" && configured !== null
      || reason === "settings_absent" && t.currency_settings_actor_id !== null) return false;
  return await revenueOriginalFingerprint(t) === v.fingerprint;
}
export async function validPriceReferences(v: unknown, institute: string, appointment: string, offset: number): Promise<boolean> {
  if (!keys(v, "institute_id appointment_id captured_at page originals legacy_service_selection_events") || v.institute_id !== institute || v.appointment_id !== appointment
    || !count(v.legacy_service_selection_events) || !Array.isArray(v.originals) || !page(v.page, offset, v.originals.length)) return false;
  const capture = instant(v.captured_at), ids = new Set(); let previous: PriceTerms | undefined;
  if (capture === undefined) return false;
  for (const r of v.originals) {
    if (!await validPriceReference(r, institute, appointment)) return false;
    const t = r.terms as PriceTerms, at = instant(t.occurred_at)!;
    if (at > capture || ids.has(t.event_id) || previous && (instant(previous.occurred_at)! > at || instant(previous.occurred_at) === at && previous.event_id >= t.event_id)) return false;
    ids.add(t.event_id); previous = t;
  }
  return true;
}
export const compatibleReference = (r: PriceReference, e: ClosureEvidence) => r.terms.institute_id === e.institute_id && r.terms.appointment_id === e.appointment_id
  && r.terms.service_id === e.after.service_id && instant(r.terms.occurred_at)! <= instant(e.occurred_at)!;
export function validClosureDeclaration(v: unknown): v is ClosureDeclaration {
  return keys(v, "valuation idempotency_key") && text(v.idempotency_key, 120) && keys(v.valuation, "reference_event_id expected_fingerprint closure_event_id rate reason")
    && id(v.valuation.reference_event_id) && digest(v.valuation.expected_fingerprint) && id(v.valuation.closure_event_id)
    && ["member", "passage"].includes(v.valuation.rate as string) && text(v.valuation.reason, 240) && Array.from(v.valuation.reason).length >= 3;
}
export async function validClosureEnvelope(v: unknown, institute: string, appointment?: string): Promise<boolean> {
  if (!keys(v, "original fingerprint") || !digest(v.fingerprint) || !keys(v.original, "id institute_id appointment_id idempotency_key actor_id created_at retained type request reference evidence estimated_value unavailable_reason confidence recommended_action causal_loss_proven action_executed reference_event")) return false;
  const o = v.original;
  if (o.institute_id !== institute || !id(o.id) || !id(o.appointment_id) || appointment !== undefined && o.appointment_id !== appointment || !text(o.actor_id, 160) || /[\x00-\x1f]/.test(o.actor_id)
    || o.retained !== true || o.type !== "review_booking_closure_reference_value" || o.confidence !== "declared_rate_scenario_not_agreed_quote"
    || o.recommended_action !== "review_actual_agreement_eligibility_and_recovery_before_action" || o.causal_loss_proven !== false || o.action_executed !== false
    || !validClosureDeclaration({ valuation: o.request, idempotency_key: o.idempotency_key }) || !validClosureEvidence(o.evidence, institute, o.appointment_id)
    || !await validPriceReference(o.reference, institute, o.appointment_id)) return false;
  const original = o as unknown as ClosureOriginal, t = original.reference.terms, e = original.evidence, request = original.request, r = original.reference_event, capture = instant(o.created_at);
  if (capture === undefined || capture !== instant(e.captured_at) || !compatibleReference(original.reference, e)
    || request.reference_event_id !== t.event_id || request.expected_fingerprint !== original.reference.fingerprint || request.closure_event_id !== e.event_id
    || !keys(r, "id institute_id appointment_id event_type occurred_at actor_id before after") || r.id !== t.event_id || r.institute_id !== institute || r.appointment_id !== o.appointment_id
    || r.event_type !== t.event_type || instant(r.occurred_at) !== instant(t.occurred_at) || r.actor_id !== t.actor_id || !state(r.after)
    || !["scheduled", "confirmed"].includes(r.after.status) || r.after.service_id !== t.service_id || !unexecuted(r.after)) return false;
  if (r.event_type === "created" ? r.before !== null || r.after.status !== "scheduled" : !state(r.before) || !["scheduled", "confirmed"].includes(r.before.status)
    || r.before.status !== r.after.status || r.before.service_id === r.after.service_id || !unexecuted(r.before)) return false;
  const quality = t[`${request.rate}_quality`], amount = t[`${request.rate}_minor`];
  const reason = t.currency === null ? "unknown_currency" : quality === "missing" ? "missing_rate" : quality === "invalid" ? "invalid_rate" : null;
  if (original.unavailable_reason !== reason || (reason !== null ? original.estimated_value !== null : !keys(original.estimated_value, "currency amount_minor basis")
    || original.estimated_value.currency !== t.currency || original.estimated_value.amount_minor !== amount || original.estimated_value.basis !== "explicit_historical_catalog_rate_scenario")) return false;
  return await revenueOriginalFingerprint(o) === v.fingerprint;
}
export const matchesClosureReceipt = (e: ClosureEnvelope, appointment: string, terms: ClosureDeclaration, signed: string) => e.original.appointment_id === appointment && e.original.actor_id === signed
  && e.original.idempotency_key === terms.idempotency_key && (Object.keys(terms.valuation) as (keyof ClosureDeclaration["valuation"])[]).every(k => e.original.request[k] === terms.valuation[k]);
export async function validClosureAudit(v: unknown, institute: string, offset: number): Promise<boolean> {
  if (!keys(v, "institute_id captured_at offset limit total originals full_original_cohort_verified causal_loss_proven action_executed") || v.institute_id !== institute
    || v.offset !== offset || v.limit !== 20 || !count(v.total) || !count(offset) || !Array.isArray(v.originals) || v.originals.length !== Math.min(20, Math.max(0, v.total-offset))
    || v.full_original_cohort_verified !== true || v.causal_loss_proven !== false || v.action_executed !== false) return false;
  const capture = instant(v.captured_at), ids = new Set(), keysSeen = new Set(); let previous: ClosureOriginal | undefined;
  if (capture === undefined) return false;
  for (const env of v.originals) {
    if (!await validClosureEnvelope(env, institute)) return false;
    const o = env.original as ClosureOriginal, at = instant(o.created_at)!;
    if (at > capture || ids.has(o.id) || keysSeen.has(o.idempotency_key) || previous && (instant(previous.created_at)! > at || instant(previous.created_at) === at && previous.id >= o.id)) return false;
    ids.add(o.id); keysSeen.add(o.idempotency_key); previous = o;
  }
  return true;
}
