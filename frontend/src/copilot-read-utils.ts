import { revenueOriginalFingerprint as hash } from "./revenue-scenario-utils";
import { certificationInstant as instant } from "./certification-utils";
import { validOutlook, type Outlook } from "./outlook-utils";
import { validSegmentProfile, type SegmentProfile } from "./crm-segment-utils";
import { validEventCandidate, type EventCandidate } from "./crm-event-utils";
import { automationTriggers, validAutomationPolicy, type AutomationRule } from "./crm-automation-utils";
import { validRevenueCapacity, type RevenueCapacity } from "./revenue-capacity-utils";
import { certificationDate } from "./certification-utils";
import { validConflictRead, type ConflictRead } from "./copilot-conflict-utils";
import { validRevenueBilling, type RevenueBilling } from "./revenue-utils";
import { validLossRead, type LossRead } from "./copilot-loss-utils";

export const readLabels = { CLIENT_READ: "Fiche cliente", CLIENT_SUMMARY: "Profil CRM observé", CLIENT_REBOOKING_OPPORTUNITIES: "Reprise de rendez-vous", PLANNING_READ: "Planning du jour", PLANNING_GAPS: "Créneaux disponibles", EMPLOYEE_CAPACITY: "Capacité enregistrée", PLANNING_CONFLICTS: "Conflits de planning", REVENUE_SUMMARY: "Revenus enregistrés", REVENUE_LOSS_ANALYSIS: "Annulations et absences", STOCK_READ: "Stock enregistré" } as const;
export type RebookingFacts = { institute_id:string;customer_id:string;captured_at:string;policy_original_id:string|null;policy_original_digest:string|null;
  rule:AutomationRule|null;candidate:EventCandidate|null;active_bookings:{appointment_id:string;service_id:string;start_at:string;end_at:string;status:string}[];
  invalid_booking_count:number;diagnostics:Record<string,number>;review:"available"|"already_booked"|"not_due"|"disabled"|"unavailable";
  complete_customer_history:false;external_message_sent:false;delivery_authorized:false;execution_authorized:false };
export type ReadName = keyof typeof readLabels;
export type ReadSelection = { customer_id?: string; service_id?: string; day?:string; employee_id?:string;resource_id?:string;start?:string;end?:string };
export type CustomerFacts = { customer_id: string; institute_id: string; display_name: string; created_at: string };
export type PlanningFacts = { generated_at: string; rows: { employee_id: string; employee_status: string;
  sessions: { id: string; employee_id: string; service_id: string; start_time: string; planned_end_time: string; status: string }[] }[] };
export type Slot = { employee_id: string; institute_id: string; available_from: string | null; available_until: string | null; reason: string;
  blocking_session_id: string | null; blocking_appointment_id: string | null; blocking_resource_id: string | null; blocking_absence_id: string | null };
export type Gaps = { captured_at: string; rows: { employee_id: string; institute_id: string; service_id: string | null; available: boolean;
  current_slot: Slot | null; upcoming_slots: Slot[] }[]; basis: "current_scheduling_engine_windows"; complete_work_hours: false; booking_authorized: false };
export type ReadEvidence = { capability: ReadName; institute_id: string; captured_at: string; read_completed_at: string;
  result: CustomerFacts | SegmentProfile | RebookingFacts | LossRead | RevenueBilling | RevenueCapacity | ConflictRead | PlanningFacts | Gaps | Outlook; fingerprint: string; integrity: "response_sha256_not_signature_or_retained_original"; complete_customer_history: false };
export type ReadResponse = { request_id: string; status: "answered" | "clarification"; answer: string; capability: ReadName | null;
  evidence: ReadEvidence | null; actions: []; framework: "ai-swiss/base@1.5.1" };
export const record = (v: unknown): v is Record<string, unknown> => !!v && typeof v === "object" && !Array.isArray(v);
export const exactKeys = (v: unknown, names: string): v is Record<string, unknown> => record(v) && Object.keys(v).sort().join(" ") === names.split(" ").sort().join(" ");
export const exactId = (v: unknown): v is string => typeof v === "string" && !!v && v.trim() === v && Array.from(v).length <= 80 && !/[\x00-\x1f]/.test(v);
const text = (v: unknown, max: number): v is string => typeof v === "string" && !!v.trim() && Array.from(v).length <= max;
const date = (v: unknown): v is string => instant(v) !== undefined;
const unique = (values: unknown[]) => new Set(values).size === values.length;
const allNames = ["CLIENT_READ", "CLIENT_SUMMARY", "CLIENT_REBOOKING_OPPORTUNITIES", "PLANNING_READ", "PLANNING_GAPS", "PLANNING_CONFLICTS", "EMPLOYEE_CAPACITY", "REVENUE_SUMMARY", "REVENUE_LOSS_ANALYSIS", "REVENUE_OPPORTUNITIES", "STOCK_READ", "STOCK_FORECAST"];
export function validReadDiscovery(value: unknown, role: string): value is { name: string }[] {
  const expected = role === "responsable_institut" ? allNames : role === "accueil" ? ["CLIENT_READ", "PLANNING_READ", "PLANNING_GAPS", "STOCK_READ", "STOCK_FORECAST"] : [];
  return Array.isArray(value) && expected.length > 0 && value.length === expected.length && unique(value.map(row => row?.name))
    && value.every(row => exactKeys(row,"name level permission input_schema output_schema application_service audit mutates")
      && expected.includes(row.name as string) && (row.level === 0 || row.level === 1) && row.mutates === false
      && ["customer_operator", "crm_manager", "planning_operator", "capacity_manager", "inventory_operator"].includes(row.permission as string)
      && record(row.input_schema) && record(row.output_schema) && text(row.application_service,240)
      && row.audit === "signed_scope_interaction_id_and_source_digest_no_raw_message");
}
export function validReadSelection(name: ReadName, selection: ReadSelection): boolean {
  const fields = Object.keys(selection).sort().join(" ");
  if(name === "REVENUE_SUMMARY" || name === "REVENUE_LOSS_ANALYSIS") return fields==="end start" && date(selection.start) && date(selection.end) && instant(selection.start)!<instant(selection.end)!;
  if(name === "PLANNING_CONFLICTS") return certificationDate(selection.day) && (fields === "day employee_id" && exactId(selection.employee_id) || fields === "day resource_id" && exactId(selection.resource_id));
  if (name === "EMPLOYEE_CAPACITY") return fields === "day" && certificationDate(selection.day);
  if (name === "CLIENT_READ" || name === "CLIENT_SUMMARY" || name === "CLIENT_REBOOKING_OPPORTUNITIES") return fields === "customer_id" && exactId(selection.customer_id);
  if (name === "PLANNING_GAPS") return fields === "" || fields === "service_id" && exactId(selection.service_id);
  return fields === "";
}
function validSlot(value: unknown, institute: string, employee: string): value is Slot {
  if (!exactKeys(value,"employee_id institute_id available_from available_until reason blocking_session_id blocking_appointment_id blocking_resource_id blocking_absence_id")
    || value.employee_id !== employee || value.institute_id !== institute || !text(value.reason,160)
    || ![value.blocking_session_id,value.blocking_appointment_id,value.blocking_resource_id,value.blocking_absence_id].every(v => v === null || exactId(v))) return false;
  return (value.available_from === null || date(value.available_from)) && (value.available_until === null || date(value.available_until))
    && (value.available_from === null || value.available_until === null || instant(value.available_from)! < instant(value.available_until)!);
}
function validFacts(name: ReadName, value: unknown, institute: string, selection: ReadSelection, capture: string, timezone?:string): boolean {
  if(name === "REVENUE_LOSS_ANALYSIS") return validLossRead(value,institute,{start:selection.start!,end:selection.end!},capture);
  if(name === "REVENUE_SUMMARY") return validRevenueBilling(value,institute,{start:selection.start!,end:selection.end!}) && instant(value.window.captured_at)===instant(capture);
  if(name === "PLANNING_CONFLICTS") return typeof timezone==="string" && validConflictRead(value,institute,selection.day!,timezone,selection.employee_id ? {employee_id:selection.employee_id} : {resource_id:selection.resource_id},capture);
  if (name === "EMPLOYEE_CAPACITY") return record(value) && typeof value.timezone === "string" && validRevenueCapacity(value,institute,selection.day!,value.timezone,0) && instant(value.window.captured_at)===instant(capture);
  if (name === "CLIENT_REBOOKING_OPPORTUNITIES") return validRebooking(value,institute,selection.customer_id!,capture);
  if (name === "CLIENT_SUMMARY") return exactKeys(value,"institute_id customer_id captured_at customer policy_original undated_paid_tickets future_paid_tickets segment unavailable_reason complete_customer_history")
    && exactKeys(value.customer,"institute_id customer_id created_at") && validSegmentProfile(value,institute,selection.customer_id!)
    && instant(value.captured_at) === instant(capture);
  if (name === "CLIENT_READ") return exactKeys(value,"customer_id institute_id display_name created_at") && value.customer_id === selection.customer_id
    && value.institute_id === institute && text(value.display_name,160) && date(value.created_at);
  if (name === "STOCK_READ") return exactKeys(value,"institute_id generated_at starts_at ends_at source coverage demands limit offset items")
    && validOutlook(value,institute,0,undefined,50) && instant(value.generated_at) === instant(capture);
  if (name === "PLANNING_READ") return exactKeys(value,"generated_at rows") && date(value.generated_at) && instant(value.generated_at) === instant(capture)
    && Array.isArray(value.rows) && unique(value.rows.map(row => row?.employee_id)) && value.rows.every(row => exactKeys(row,"employee_id employee_status sessions")
      && exactId(row.employee_id) && text(row.employee_status,80) && Array.isArray(row.sessions) && unique(row.sessions.map(s => s?.id))
      && row.sessions.every(s => exactKeys(s,"id employee_id service_id start_time planned_end_time status") && exactId(s.id) && s.employee_id === row.employee_id
        && exactId(s.service_id) && date(s.start_time) && date(s.planned_end_time) && instant(s.start_time)! < instant(s.planned_end_time)! && text(s.status,80)));
  return exactKeys(value,"captured_at rows basis complete_work_hours booking_authorized") && date(value.captured_at) && instant(value.captured_at) === instant(capture)
    && value.basis === "current_scheduling_engine_windows" && value.complete_work_hours === false && value.booking_authorized === false
    && Array.isArray(value.rows) && unique(value.rows.map(row => row?.employee_id)) && value.rows.every(row => exactKeys(row,"employee_id institute_id service_id available current_slot upcoming_slots")
      && exactId(row.employee_id) && row.institute_id === institute && row.service_id === (selection.service_id ?? null) && typeof row.available === "boolean"
      && (row.current_slot === null || validSlot(row.current_slot,institute,row.employee_id)) && Array.isArray(row.upcoming_slots)
      && row.upcoming_slots.every(slot => validSlot(slot,institute,row.employee_id as string)));
}
function validRebooking(v:unknown,institute:string,customer:string,capture:string):boolean {
  if (!exactKeys(v,"institute_id customer_id captured_at policy_original_id policy_original_digest rule candidate active_bookings invalid_booking_count diagnostics review complete_customer_history external_message_sent delivery_authorized execution_authorized")
    || v.institute_id!==institute || v.customer_id!==customer || !date(v.captured_at) || instant(v.captured_at)!==instant(capture)
    || [v.complete_customer_history,v.external_message_sent,v.delivery_authorized,v.execution_authorized].some(flag=>flag!==false)
    || !Number.isSafeInteger(v.invalid_booking_count) || (v.invalid_booking_count as number)<0) return false;
  if (v.policy_original_id===null ? v.policy_original_digest!==null : !exactId(v.policy_original_id) || typeof v.policy_original_digest!=="string" || !/^[0-9a-f]{64}$/.test(v.policy_original_digest)) return false;
  if (v.rule!==null) {
    if (!exactKeys(v.rule,"trigger enabled offset_us") || v.rule.trigger!=="rebooking" || v.policy_original_id===null) return false;
    const rules=automationTriggers.map(trigger=>trigger==="rebooking" ? v.rule : {trigger,enabled:false,offset_us:trigger==="inactivity" ? "1" : "0"});
    if(!validAutomationPolicy({institute_id:institute,rules},institute))return false;
  }
  const c=v.candidate;
  if(c!==null && (!exactKeys(c,"institute_id customer_id policy_original_id rule source due_at valid_until captured_at state external_message_sent delivery_authorized")
    || !exactKeys(c.source,"institute_id customer_id source_id source_kind occurred_at expires_at remaining") || !exactKeys(c.rule,"trigger enabled offset_us")
    || !validEventCandidate(c,institute,customer) || c.source.source_kind!=="care_episode" || c.policy_original_id!==v.policy_original_id
    || instant(c.captured_at)!==instant(capture) || !record(v.rule) || c.rule.trigger!==v.rule.trigger || c.rule.enabled!==v.rule.enabled || c.rule.offset_us!==v.rule.offset_us))return false;
  if(!Array.isArray(v.active_bookings) || !unique(v.active_bookings.map(b=>b?.appointment_id)) || !v.active_bookings.every(b=>exactKeys(b,"appointment_id service_id start_at end_at status")
    && exactId(b.appointment_id) && exactId(b.service_id) && date(b.start_at) && date(b.end_at) && instant(b.start_at)!<instant(b.end_at)!
    && instant(b.end_at)!>instant(capture)! && ["scheduled","confirmed","arrived","in_progress"].includes(b.status as string)))return false;
  const diagnostics=["policy_absent","future_policy","future_registration","care_unavailable","care_unlinked_ticket","care_invalid_owner_or_service","care_invalid_actual_times","invalid_event_timing"];
  if(!record(v.diagnostics) || Object.entries(v.diagnostics).some(([key,count])=>!diagnostics.includes(key) || !Number.isSafeInteger(count) || (count as number)<0))return false;
  const expected=c!==null && record(c) && v.invalid_booking_count===0 ? c.state==="scheduled" ? "not_due" : c.state==="disabled" ? "disabled" : c.state==="due" ? v.active_bookings.length ? "already_booked" : "available" : "unavailable" : "unavailable";
  return v.review===expected;
}
export async function validReadResponse(value: unknown, institute: string, name: ReadName, selection: ReadSelection, timezone?:string): Promise<boolean> {
  try {
    if (!validReadSelection(name,selection) || !exactKeys(value,"request_id status answer capability evidence actions framework")
      || !text(value.request_id,80) || !text(value.answer,10000) || !Array.isArray(value.actions) || value.actions.length || value.framework !== "ai-swiss/base@1.5.1") return false;
    if (value.status === "clarification") return value.evidence === null && (value.capability === null || value.capability === name);
    if (value.status !== "answered" || value.capability !== name || !exactKeys(value.evidence,"capability institute_id captured_at read_completed_at result fingerprint integrity complete_customer_history")) return false;
    const evidence = value.evidence;
    if (evidence.capability !== name || evidence.institute_id !== institute || !date(evidence.captured_at) || !date(evidence.read_completed_at)
      || instant(evidence.read_completed_at)! < instant(evidence.captured_at)! || evidence.integrity !== "response_sha256_not_signature_or_retained_original"
      || evidence.complete_customer_history !== false || typeof evidence.fingerprint !== "string" || !/^[0-9a-f]{64}$/.test(evidence.fingerprint)
      || !validFacts(name,evidence.result,institute,selection,evidence.captured_at,timezone)) return false;
    const { fingerprint, ...payload } = evidence;
    return await hash(payload) === fingerprint;
  } catch { return false; }
}
