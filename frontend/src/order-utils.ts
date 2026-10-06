import { stockMilli, stockQuantity, stockUnits } from "./inventory-utils";
export type PurchaseEntry = { item_id: string; unit: keyof typeof stockUnits; quantity: string };
export type OrderEntry = PurchaseEntry & { item_name: string; item_sku: string };
export type PurchaseIntent = { entries: PurchaseEntry[]; reason: string; idempotency_key: string; supplier_id?: string; reference?: string };
export type Order = { id: string; institute_id: string; supplier_id: string; supplier_reference: string; supplier_name: string; reference: string; reason: string; actor_id: string; idempotency_key: string; created_at: string; entries: OrderEntry[] };
export type Receipt = { id: string; institute_id: string; order_id: string; reason: string; actor_id: string; idempotency_key: string; occurred_at: string; entries: Array<PurchaseEntry & { movement_id: string }> };
export type Progress = { institute_id: string; order_id: string; state: "pending" | "partial" | "received"; entries: Array<OrderEntry & { received: string; remaining: string }> };
export const purchaseText = (value: unknown, max: number, min = 1): value is string => typeof value === "string" && value === value.trim() && value.length >= min && value.length <= max;
export const purchaseReference = (value: unknown): value is string => purchaseText(value, 80) && /^[A-Za-z0-9][A-Za-z0-9._-]*$/.test(value);
const instant = (value: unknown) => typeof value === "string" && /(?:Z|[+-]\d{2}:\d{2})$/.test(value) && Number.isFinite(Date.parse(value));
const exact = (value: unknown, unit: string) => typeof value === "string" && /^(0|[1-9]\d{0,11})\.\d{3}$/.test(value) && stockQuantity(value, unit) === value;
export function validPurchaseEntries(value: unknown): value is PurchaseEntry[] {
  return Array.isArray(value) && value.length > 0 && value.length <= 50 && value.every(row => !!row && purchaseText(row.item_id, 80) && Object.prototype.hasOwnProperty.call(stockUnits, row.unit) && exact(row.quantity, row.unit) && stockMilli(row.quantity) > 0n) && new Set(value.map(row => row.item_id)).size === value.length;
}
export const purchaseTerms = (rows: PurchaseEntry[]) => JSON.stringify(rows.map(row => [row.item_id, row.unit, row.quantity]).sort((a, b) => a[0].localeCompare(b[0])));
export function validPurchaseIntent(value: unknown, kind: "order" | "receipt"): value is PurchaseIntent {
  const row = value as PurchaseIntent;
  return !!row && validPurchaseEntries(row.entries) && purchaseText(row.reason, 240, 3) && purchaseText(row.idempotency_key, 120) && (kind === "order" ? purchaseText(row.supplier_id, 80) && purchaseReference(row.reference) : row.supplier_id === undefined && row.reference === undefined);
}
export function validOrder(value: unknown, institute: string): value is Order {
  const row = value as Order;
  return !!row && row.institute_id === institute && purchaseText(row.id, 80) && validPurchaseIntent(row, "order") && purchaseReference(row.supplier_reference) && purchaseText(row.supplier_name, 120) && purchaseText(row.actor_id, 160) && instant(row.created_at) && row.entries.every(entry => purchaseText(entry.item_name, 120) && purchaseReference(entry.item_sku));
}
export const orderSignature = (row: Order) => JSON.stringify([row.id, row.institute_id, row.supplier_id, row.supplier_reference, row.supplier_name, row.reference, row.reason, row.actor_id, row.idempotency_key, row.created_at, [...row.entries].sort((a, b) => a.item_id.localeCompare(b.item_id))]);
export function validReceipt(value: unknown, order: Order): value is Receipt {
  const row = value as Receipt;
  return !!row && row.institute_id === order.institute_id && row.order_id === order.id && purchaseText(row.id, 80) && validPurchaseEntries(row.entries) && purchaseText(row.reason, 240, 3) && purchaseText(row.idempotency_key, 120) && purchaseText(row.actor_id, 160) && instant(row.occurred_at) && row.entries.every(entry => {
    const original = order.entries.find(item => item.item_id === entry.item_id);
    return original && original.unit === entry.unit && stockMilli(entry.quantity) <= stockMilli(original.quantity) && purchaseText(entry.movement_id, 80);
  }) && new Set(row.entries.map(row => row.movement_id)).size === row.entries.length;
}
export function validProgress(value: unknown, order: Order): value is Progress {
  const row = value as Progress;
  if (!row || row.institute_id !== order.institute_id || row.order_id !== order.id || !validPurchaseEntries(row.entries) || purchaseTerms(row.entries) !== purchaseTerms(order.entries) || row.entries.length !== order.entries.length) return false;
  if (!row.entries.every(entry => { const original = order.entries.find(item => item.item_id === entry.item_id); return original && entry.item_name === original.item_name && entry.item_sku === original.item_sku && exact(entry.received, entry.unit) && exact(entry.remaining, entry.unit) && stockMilli(entry.received) + stockMilli(entry.remaining) === stockMilli(entry.quantity); })) return false;
  return row.state === (row.entries.every(entry => stockMilli(entry.remaining) === 0n) ? "received" : row.entries.some(entry => stockMilli(entry.received) > 0n) ? "partial" : "pending");
}
export const matchesPurchase = (row: Order | Receipt, intent: PurchaseIntent, actor: string) => row.actor_id === actor && row.reason === intent.reason && row.idempotency_key === intent.idempotency_key && purchaseTerms(row.entries) === purchaseTerms(intent.entries) && ("supplier_id" in row ? row.supplier_id === intent.supplier_id && row.reference === intent.reference : intent.supplier_id === undefined);
