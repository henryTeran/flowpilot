import { stockMilli, stockUnits } from "./inventory-utils";
import { validEntries, recipeTerms, type RecipeEntry } from "./recipe-utils";
export type Work = { billing_state: "active" | "removed" | "not_issued" | "unknown"; invoice_removed_at: string | null; employee_name: string; ticket_number: string | null; basis_id: string; institute_id: string; source_kind: "sessions" | "appointments"; source_id: string; source_status: string; service_id: string; service_name: string; quantity: number; state: "enabled" | "disabled" | "unconfigured"; captured_at: string; completed_at: string | null; consumption_id: string | null };
export type Consumption = { id: string; institute_id: string; basis_id: string; actor_id: string; reason: string; idempotency_key: string; entries: Array<RecipeEntry & { movement_id: string }>; expected_entries: RecipeEntry[] | null; matches_norm: boolean | null; created_at: string };
export type WorkDetail = Work & { expected_entries: RecipeEntry[] | null; consumption: Consumption | null };
export type ConsumptionIntent = { basis_name: string; basis_state: Work["state"]; expected_entries: RecipeEntry[] | null; no_material: boolean; entries: Array<RecipeEntry & { name: string; sku: string }>; reason: string; idempotency_key: string };
const id = (value: unknown) => typeof value === "string" && !!value.trim() && value === value.trim() && value.length <= 80;
const text = (value: unknown, max: number, min = 1) => typeof value === "string" && value.trim().length >= min && value.length <= max;
const instant = (value: unknown) => typeof value === "string" && /(?:Z|[+-]\d{2}:\d{2})$/.test(value) && Number.isFinite(Date.parse(value));
export const normTerms = (entries: RecipeEntry[] | null) => entries === null ? "unconfigured" : recipeTerms(entries);
export function validNorm(entries: unknown): entries is RecipeEntry[] | null {
  return entries === null || (Array.isArray(entries) && entries.length <= 50 && entries.every(row => !!row && id(row.item_id) && Object.prototype.hasOwnProperty.call(stockUnits, row.unit) && typeof row.quantity === "string" && /^(0|[1-9]\d{0,24})\.\d{3}$/.test(row.quantity) && stockMilli(row.quantity) > 0n && (row.unit !== "unit" || stockMilli(row.quantity) % 1000n === 0n)) && new Set(entries.map(row => row.item_id)).size === entries.length);
}
const stateNorm = (state: string, entries: RecipeEntry[] | null) => state === "unconfigured" ? entries === null : entries !== null && (state === "enabled" ? entries.length > 0 : entries.length === 0);
export function validWork(value: unknown, institute: string): value is Work {
  const row = value as Work;
  return !!row && ["active", "removed", "not_issued", "unknown"].includes(row.billing_state) && (row.billing_state === "removed" ? instant(row.invoice_removed_at) : row.invoice_removed_at === null) && text(row.employee_name, 120) && (row.ticket_number === null || text(row.ticket_number, 40)) && id(row.basis_id) && row.institute_id === institute && ["sessions", "appointments"].includes(row.source_kind) && id(row.source_id) && text(row.source_status, 40) && id(row.service_id) && text(row.service_name, 160) && Number.isSafeInteger(row.quantity) && row.quantity >= 1 && row.quantity <= 2147483647 && ["enabled", "disabled", "unconfigured"].includes(row.state) && instant(row.captured_at) && (row.completed_at === null || instant(row.completed_at)) && (row.consumption_id === null || id(row.consumption_id));
}
export function validConsumption(value: unknown, institute: string, basis: string): value is Consumption {
  const row = value as Consumption;
  return !!row && id(row.id) && row.institute_id === institute && row.basis_id === basis && text(row.actor_id, 160) && text(row.reason, 240, 3) && text(row.idempotency_key, 120) && instant(row.created_at) && validEntries(row.entries) && row.entries.every(entry => id((entry as Consumption["entries"][0]).movement_id)) && new Set(row.entries.map(entry => entry.movement_id)).size === row.entries.length && validNorm(row.expected_entries) && row.matches_norm === (row.expected_entries === null ? null : recipeTerms(row.entries) === recipeTerms(row.expected_entries));
}
export function validWorkDetail(value: unknown, institute: string, basis: string): value is WorkDetail {
  const row = value as WorkDetail;
  return validWork(row, institute) && row.basis_id === basis && validNorm(row.expected_entries) && stateNorm(row.state, row.expected_entries) && (row.consumption === null ? row.consumption_id === null : validConsumption(row.consumption, institute, basis) && row.consumption.id === row.consumption_id && normTerms(row.expected_entries) === normTerms(row.consumption.expected_entries));
}
export function validConsumptionIntent(row: ConsumptionIntent): boolean {
  return !!row && text(row.basis_name, 160) && ["enabled", "disabled", "unconfigured"].includes(row.basis_state) && validNorm(row.expected_entries) && stateNorm(row.basis_state, row.expected_entries) && typeof row.no_material === "boolean" && validEntries(row.entries) && row.no_material === (row.entries.length === 0) && row.entries.every(entry => text(entry.name, 120) && typeof entry.sku === "string" && /^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$/.test(entry.sku)) && text(row.reason, 240, 3) && text(row.idempotency_key, 120);
}
export function matchesConsumption(row: Consumption, intent: ConsumptionIntent, actor: string) {
  return row.actor_id === actor && row.reason === intent.reason && row.idempotency_key === intent.idempotency_key && recipeTerms(row.entries) === recipeTerms(intent.entries) && normTerms(row.expected_entries) === normTerms(intent.expected_entries);
}
export type NamedEntry = RecipeEntry & { name: string; sku: string };

export const billingCaption = (state: Work["billing_state"]) => ({ active: "Présente sur la facture", removed: "Retirée de la facture", not_issued: "Facture non émise", unknown: "Lien de facture d’origine non établi" }[state]);
