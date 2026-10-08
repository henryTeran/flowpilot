import { certificationInstant as instant } from "./certification-utils";
import { revenueOriginalFingerprint as hash } from "./revenue-scenario-utils";

export type BaseSnapshot = { status: "scheduled" | "confirmed" | "arrived"; employee_id: string; service_id: string;
  customer_id: string | null; start_time: string; end_time: string; booked_start_time: string | null;
  booked_end_time: string | null; actual_start_time: string | null; actual_end_time: string | null; checkout_ticket_id: string | null };
export type BasePreview = { principal: { actor_id: string; institute_id: string; role: "responsable_institut" };
  capability: { name: "APPOINTMENT_CANCEL"; prepare_level: 2; execution_level: 3; roles: ["responsable_institut"];
    application_service: "appointments.service.cancel_appointment";
    approval: "explicit_human_approval_of_exact_retained_operation_required"; public_execution: false };
  appointment_id: string; captured_at: string; appointment: BaseSnapshot; booking_events: number;
  booking_history_fingerprint: string; state_fingerprint: string; effect: "cancellation_preview_only_no_approval_or_execution" };
export type BaseOperationRequest = { capability: "APPOINTMENT_CANCEL"; selection: { appointment_id: string };
  expected_state_fingerprint: string; valid_until: string; reason: string; idempotency_key: string };
export type BaseOperation = BaseOperationRequest & { id: string; institute_id: string; actor_id: string; created_at: string;
  preview: BasePreview; effect: "prepared_sensitive_operation_only_pending_human_approval_no_execution" };
export type BaseEnvelope<T> = { original: T; fingerprint: string };
export type BaseOperationEnvelope = BaseEnvelope<BaseOperation>;
export type BaseDecisionRequest = { operation_id: string; operation_fingerprint: string; previous_id: string | null;
  previous_fingerprint: string | null; decision: "approve" | "decline" | "revoke"; reason: string; idempotency_key: string };
export type BaseDecision = BaseDecisionRequest & { id: string; institute_id: string; actor_id: string; created_at: string;
  source_checked_at: string | null; checked_state_fingerprint: string | null; effect: "explicit_signed_human_decision_only_no_execution" };
export type BaseDecisionEnvelope = BaseEnvelope<BaseDecision>;
export type BaseApprovalState = { operation: BaseOperationEnvelope; captured_at: string; decisions: BaseDecisionEnvelope[];
  status: "pending" | "approved" | "declined" | "revoked"; expired: boolean;
  execution: "not_performed_by_approval_manager"; current_source: "not_revalidated_by_historical_state_read" };
export type BaseExecutionRequest = { operation_id: string; operation_fingerprint: string; approval_id: string;
  approval_fingerprint: string; reason: string; idempotency_key: string };
export type BaseExecution = BaseExecutionRequest & { id: string; institute_id: string; actor_id: string; created_at: string;
  before: BasePreview; after: Omit<BaseSnapshot, "status"> & { status: "cancelled" }; booking_event_id: string;
  booking_event_fingerprint: string; effect: "appointment_cancelled_through_existing_service_no_contact_or_refund" };
export type BaseExecutionEnvelope = BaseEnvelope<BaseExecution>;

const keys = (v: unknown, names: string): v is Record<string, any> => !!v && typeof v === "object" && !Array.isArray(v)
  && Object.keys(v).sort().join(" ") === names.split(" ").sort().join(" ");
const id = (v: unknown, max = 80, min = 1): v is string => typeof v === "string" && v === v.trim()
  && Array.from(v).length >= min && Array.from(v).length <= max && !/[\x00-\x1f]/.test(v);
const digest = (v: unknown): v is string => typeof v === "string" && /^[0-9a-f]{64}$/.test(v);
const count = (v: unknown): v is number => typeof v === "number" && Number.isSafeInteger(v) && v >= 0;
const utc = (v: unknown): v is string => typeof v === "string"
  && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.(?!000000)\d{6})?Z$/.test(v) && instant(v) !== undefined;
const nullableId = (v: unknown) => v === null || id(v);
const nullableTime = (v: unknown) => v === null || utc(v);
const terms = (v: Record<string, any>) => id(v.reason, 240, 3) && id(v.idempotency_key, 120);
const identity = (v: Record<string, any>, institute: string) => id(v.id) && v.institute_id === institute && id(institute)
  && id(v.actor_id, 160) && utc(v.created_at);
const same = async (a: unknown, b: unknown) => await hash(a) === await hash(b);

export function validBaseSnapshot(v: unknown, cancelled = false): boolean {
  return keys(v, "status employee_id service_id customer_id start_time end_time booked_start_time booked_end_time actual_start_time actual_end_time checkout_ticket_id")
    && (cancelled ? v.status === "cancelled" : ["scheduled", "confirmed", "arrived"].includes(v.status))
    && id(v.employee_id) && id(v.service_id) && nullableId(v.customer_id) && nullableId(v.checkout_ticket_id)
    && utc(v.start_time) && utc(v.end_time) && instant(v.end_time)! > instant(v.start_time)!
    && [v.booked_start_time, v.booked_end_time, v.actual_start_time, v.actual_end_time].every(nullableTime);
}

export async function validBasePreview(v: unknown, institute: string, appointment?: string): Promise<boolean> {
  try {
    if (!keys(v, "principal capability appointment_id captured_at appointment booking_events booking_history_fingerprint state_fingerprint effect")
      || !keys(v.principal, "actor_id institute_id role") || v.principal.institute_id !== institute || !id(institute)
      || !id(v.principal.actor_id, 160) || v.principal.role !== "responsable_institut" || !id(v.appointment_id)
      || appointment !== undefined && v.appointment_id !== appointment || !utc(v.captured_at) || !validBaseSnapshot(v.appointment)
      || !count(v.booking_events) || !digest(v.booking_history_fingerprint) || !digest(v.state_fingerprint)
      || v.effect !== "cancellation_preview_only_no_approval_or_execution"
      || !keys(v.capability, "name prepare_level execution_level roles application_service approval public_execution")) return false;
    const c = v.capability;
    if (c.name !== "APPOINTMENT_CANCEL" || c.prepare_level !== 2 || c.execution_level !== 3 || !Array.isArray(c.roles)
      || c.roles.length !== 1 || c.roles[0] !== "responsable_institut" || c.application_service !== "appointments.service.cancel_appointment"
      || c.approval !== "explicit_human_approval_of_exact_retained_operation_required" || c.public_execution !== false) return false;
    return await hash({ institute_id: institute, appointment_id: v.appointment_id, appointment: v.appointment,
      booking_events: v.booking_events, booking_history_fingerprint: v.booking_history_fingerprint }) === v.state_fingerprint;
  } catch { return false; }
}

export function validBaseOperationRequest(v: unknown): v is BaseOperationRequest {
  return keys(v, "capability selection expected_state_fingerprint valid_until reason idempotency_key") && terms(v)
    && v.capability === "APPOINTMENT_CANCEL" && keys(v.selection, "appointment_id") && id(v.selection.appointment_id)
    && digest(v.expected_state_fingerprint) && utc(v.valid_until);
}
export function validBaseDecisionRequest(v: unknown): v is BaseDecisionRequest {
  return keys(v, "operation_id operation_fingerprint previous_id previous_fingerprint decision reason idempotency_key") && terms(v)
    && id(v.operation_id) && digest(v.operation_fingerprint) && nullableId(v.previous_id)
    && (v.previous_id === null ? v.previous_fingerprint === null : digest(v.previous_fingerprint))
    && ["approve", "decline", "revoke"].includes(v.decision);
}
export function validBaseExecutionRequest(v: unknown): v is BaseExecutionRequest {
  return keys(v, "operation_id operation_fingerprint approval_id approval_fingerprint reason idempotency_key") && terms(v)
    && id(v.operation_id) && id(v.approval_id) && digest(v.operation_fingerprint) && digest(v.approval_fingerprint);
}

export async function validBaseOperationEnvelope(v: unknown, institute: string): Promise<boolean> {
  try {
    if (!keys(v, "original fingerprint") || !digest(v.fingerprint)
      || !keys(v.original, "capability selection expected_state_fingerprint valid_until reason idempotency_key id institute_id actor_id created_at preview effect")) return false;
    const o = v.original;
    return identity(o, institute) && validBaseOperationRequest({ capability: o.capability, selection: o.selection,
      expected_state_fingerprint: o.expected_state_fingerprint, valid_until: o.valid_until, reason: o.reason, idempotency_key: o.idempotency_key })
      && o.effect === "prepared_sensitive_operation_only_pending_human_approval_no_execution"
      && await validBasePreview(o.preview, institute, o.selection.appointment_id) && o.preview.principal.actor_id === o.actor_id
      && o.preview.state_fingerprint === o.expected_state_fingerprint && instant(o.preview.captured_at)! <= instant(o.created_at)!
      && instant(o.created_at)! < instant(o.valid_until)! && await hash(o) === v.fingerprint;
  } catch { return false; }
}

export async function validBaseDecisionEnvelope(v: unknown, institute: string, operation: BaseOperationEnvelope): Promise<boolean> {
  try {
    if (!await validBaseOperationEnvelope(operation, institute) || !keys(v, "original fingerprint") || !digest(v.fingerprint)
      || !keys(v.original, "operation_id operation_fingerprint previous_id previous_fingerprint decision reason idempotency_key id institute_id actor_id created_at source_checked_at checked_state_fingerprint effect")) return false;
    const o = v.original, op = operation.original;
    if (!identity(o, institute) || !validBaseDecisionRequest({ operation_id: o.operation_id, operation_fingerprint: o.operation_fingerprint,
      previous_id: o.previous_id, previous_fingerprint: o.previous_fingerprint, decision: o.decision, reason: o.reason, idempotency_key: o.idempotency_key })
      || o.operation_id !== op.id || o.operation_fingerprint !== operation.fingerprint || o.id === o.previous_id
      || instant(o.created_at)! < instant(op.created_at)! || o.effect !== "explicit_signed_human_decision_only_no_execution") return false;
    if (o.decision === "approve") {
      if (!utc(o.source_checked_at) || o.checked_state_fingerprint !== op.expected_state_fingerprint
        || instant(o.source_checked_at)! < instant(op.created_at)! || instant(o.source_checked_at)! > instant(o.created_at)!
        || instant(o.created_at)! >= instant(op.valid_until)!) return false;
    } else if (o.source_checked_at !== null || o.checked_state_fingerprint !== null) return false;
    return await hash(o) === v.fingerprint;
  } catch { return false; }
}

export async function validBaseApprovalState(v: unknown, institute: string, selected?: BaseOperationEnvelope): Promise<boolean> {
  try {
    if (!keys(v, "operation captured_at decisions status expired execution current_source") || !utc(v.captured_at)
      || !await validBaseOperationEnvelope(v.operation, institute) || !Array.isArray(v.decisions) || v.decisions.length > 2
      || v.execution !== "not_performed_by_approval_manager" || v.current_source !== "not_revalidated_by_historical_state_read"
      || typeof v.expired !== "boolean") return false;
    const op = v.operation as BaseOperationEnvelope, capture = instant(v.captured_at)!;
    if (selected && (selected.original.id !== op.original.id || selected.fingerprint !== op.fingerprint)
      || capture < instant(op.original.created_at)! || v.expired !== (capture >= instant(op.original.valid_until)!)) return false;
    let status = "pending", previous: BaseDecisionEnvelope | undefined;
    const ids = new Set<string>(), savedKeys = new Set<string>();
    for (const entry of v.decisions as BaseDecisionEnvelope[]) {
      if (!await validBaseDecisionEnvelope(entry, institute, op)) return false;
      const o = entry.original;
      if (ids.has(o.id) || savedKeys.has(o.idempotency_key) || instant(o.created_at)! > capture
        || o.previous_id !== (previous?.original.id ?? null) || o.previous_fingerprint !== (previous?.fingerprint ?? null)
        || previous && instant(o.created_at)! < instant(previous.original.created_at)!
        || !(status === "pending" && ["approve", "decline"].includes(o.decision) || status === "approved" && o.decision === "revoke")) return false;
      ids.add(o.id); savedKeys.add(o.idempotency_key); previous = entry;
      status = { approve: "approved", decline: "declined", revoke: "revoked" }[o.decision];
    }
    return v.status === status;
  } catch { return false; }
}

export async function validBaseExecutionEnvelope(v: unknown, institute: string, state: BaseApprovalState): Promise<boolean> {
  try {
    if (!await validBaseApprovalState(state, institute) || state.status !== "approved"
      || !keys(v, "original fingerprint") || !digest(v.fingerprint)
      || !keys(v.original, "operation_id operation_fingerprint approval_id approval_fingerprint reason idempotency_key id institute_id actor_id created_at before after booking_event_id booking_event_fingerprint effect")) return false;
    const o = v.original, op = state.operation, approval = state.decisions[state.decisions.length-1];
    return identity(o, institute) && validBaseExecutionRequest({ operation_id: o.operation_id, operation_fingerprint: o.operation_fingerprint,
      approval_id: o.approval_id, approval_fingerprint: o.approval_fingerprint, reason: o.reason, idempotency_key: o.idempotency_key })
      && o.operation_id === op.original.id && o.operation_fingerprint === op.fingerprint
      && o.approval_id === approval.original.id && o.approval_fingerprint === approval.fingerprint
      && o.effect === "appointment_cancelled_through_existing_service_no_contact_or_refund" && id(o.booking_event_id) && digest(o.booking_event_fingerprint)
      && await validBasePreview(o.before, institute, op.original.selection.appointment_id) && o.before.principal.actor_id === o.actor_id
      && o.before.state_fingerprint === op.original.expected_state_fingerprint && validBaseSnapshot(o.after, true)
      && await same(o.after, { ...o.before.appointment, status: "cancelled" })
      && instant(approval.original.created_at)! <= instant(o.before.captured_at)! && instant(o.before.captured_at)! <= instant(o.created_at)!
      && instant(o.created_at)! < instant(op.original.valid_until)! && instant(o.created_at)! <= instant(state.captured_at)!
      && await hash(o) === v.fingerprint;
  } catch { return false; }
}
