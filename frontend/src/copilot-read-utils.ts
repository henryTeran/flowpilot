import { revenueOriginalFingerprint as hash } from "./revenue-scenario-utils";
import { certificationInstant as instant } from "./certification-utils";
import { validOutlook, type Outlook } from "./outlook-utils";
import { validSegmentProfile, type SegmentProfile } from "./crm-segment-utils";

export const readLabels = { CLIENT_READ: "Fiche cliente", CLIENT_SUMMARY: "Profil CRM observé", PLANNING_READ: "Planning du jour", PLANNING_GAPS: "Créneaux disponibles", STOCK_READ: "Stock enregistré" } as const;
export type ReadName = keyof typeof readLabels;
export type ReadSelection = { customer_id?: string; service_id?: string };
export type CustomerFacts = { customer_id: string; institute_id: string; display_name: string; created_at: string };
export type PlanningFacts = { generated_at: string; rows: { employee_id: string; employee_status: string;
  sessions: { id: string; employee_id: string; service_id: string; start_time: string; planned_end_time: string; status: string }[] }[] };
export type Slot = { employee_id: string; institute_id: string; available_from: string | null; available_until: string | null; reason: string;
  blocking_session_id: string | null; blocking_appointment_id: string | null; blocking_resource_id: string | null; blocking_absence_id: string | null };
export type Gaps = { captured_at: string; rows: { employee_id: string; institute_id: string; service_id: string | null; available: boolean;
  current_slot: Slot | null; upcoming_slots: Slot[] }[]; basis: "current_scheduling_engine_windows"; complete_work_hours: false; booking_authorized: false };
export type ReadEvidence = { capability: ReadName; institute_id: string; captured_at: string; read_completed_at: string;
  result: CustomerFacts | SegmentProfile | PlanningFacts | Gaps | Outlook; fingerprint: string; integrity: "response_sha256_not_signature_or_retained_original"; complete_customer_history: false };
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
  if (name === "CLIENT_READ" || name === "CLIENT_SUMMARY") return fields === "customer_id" && exactId(selection.customer_id);
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
function validFacts(name: ReadName, value: unknown, institute: string, selection: ReadSelection, capture: string): boolean {
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
export async function validReadResponse(value: unknown, institute: string, name: ReadName, selection: ReadSelection): Promise<boolean> {
  try {
    if (!validReadSelection(name,selection) || !exactKeys(value,"request_id status answer capability evidence actions framework")
      || !text(value.request_id,80) || !text(value.answer,10000) || !Array.isArray(value.actions) || value.actions.length || value.framework !== "ai-swiss/base@1.5.1") return false;
    if (value.status === "clarification") return value.evidence === null && (value.capability === null || value.capability === name);
    if (value.status !== "answered" || value.capability !== name || !exactKeys(value.evidence,"capability institute_id captured_at read_completed_at result fingerprint integrity complete_customer_history")) return false;
    const evidence = value.evidence;
    if (evidence.capability !== name || evidence.institute_id !== institute || !date(evidence.captured_at) || !date(evidence.read_completed_at)
      || instant(evidence.read_completed_at)! < instant(evidence.captured_at)! || evidence.integrity !== "response_sha256_not_signature_or_retained_original"
      || evidence.complete_customer_history !== false || typeof evidence.fingerprint !== "string" || !/^[0-9a-f]{64}$/.test(evidence.fingerprint)
      || !validFacts(name,evidence.result,institute,selection,evidence.captured_at)) return false;
    const { fingerprint, ...payload } = evidence;
    return await hash(payload) === fingerprint;
  } catch { return false; }
}
