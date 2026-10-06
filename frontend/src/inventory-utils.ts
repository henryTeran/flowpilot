export type StockItem = { id: string; institute_id: string; sku: string; name: string; category: "retail" | "cabine" | "consumable"; unit: "ml" | "g" | "unit"; reorder_threshold: string; on_hand: string; at_or_below_threshold: boolean; actor_id: string; created_at: string };
export type StockMovement = { id: string; institute_id: string; item_id: string; kind: "receipt" | "adjustment"; quantity: string; unit: StockItem["unit"]; reason: string; actor_id: string; idempotency_key: string; occurred_at: string };
export const stockCategories = { retail: "Vente", cabine: "Cabine", consumable: "Consommables" };
export const stockUnits = { ml: "ml", g: "g", unit: "unités" };
const maximum = 999999999999999n;
export const stockMilli = (value: string) => BigInt(value.replace(".", ""));
export const stockDisplay = (value: string) => value.replace(".", ",");
const identifier = (value: unknown): value is string => typeof value === "string" && !!value.trim() && value === value.trim() && value.length <= 80;
const instant = (value: unknown) => typeof value === "string" && /(?:Z|[+-]\d{2}:\d{2})$/.test(value) && Number.isFinite(Date.parse(value));
function exact(value: unknown, signed = false): value is string {
  return typeof value === "string" && (signed ? /^-?(0|[1-9]\d{0,11})\.\d{3}$/ : /^(0|[1-9]\d{0,11})\.\d{3}$/).test(value) && stockMilli(value) >= (signed ? -maximum : 0n) && stockMilli(value) <= maximum;
}
export function stockQuantity(input: string, unit: string, signed = false): string | undefined {
  const value = input.trim().replace(",", ".");
  if (!(signed ? /^-?(0|[1-9]\d{0,11})(\.\d{1,3})?$/ : /^(0|[1-9]\d{0,11})(\.\d{1,3})?$/).test(value)) return;
  const [whole, fraction = ""] = value.split(".");
  const normalized = `${whole}.${fraction.padEnd(3, "0")}`;
  if (!exact(normalized, signed) || (unit === "unit" && stockMilli(normalized) % 1000n !== 0n)) return;
  return stockMilli(normalized) === 0n ? "0.000" : normalized;
}
export function validStockItem(value: unknown, institute: string): value is StockItem {
  const row = value as StockItem;
  return !!row && identifier(row.id) && row.institute_id === institute && typeof row.sku === "string" && /^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$/.test(row.sku) && typeof row.name === "string" && !!row.name.trim() && row.name.length <= 120 &&
    Object.prototype.hasOwnProperty.call(stockCategories, row.category) && Object.prototype.hasOwnProperty.call(stockUnits, row.unit) && exact(row.reorder_threshold) && exact(row.on_hand) &&
    (row.unit !== "unit" || (stockMilli(row.on_hand) % 1000n === 0n && stockMilli(row.reorder_threshold) % 1000n === 0n)) &&
    row.at_or_below_threshold === (stockMilli(row.on_hand) <= stockMilli(row.reorder_threshold)) && typeof row.actor_id === "string" && !!row.actor_id.trim() && instant(row.created_at);
}
export function validStockMovement(value: unknown, item: StockItem): value is StockMovement {
  const row = value as StockMovement;
  return !!row && identifier(row.id) && row.institute_id === item.institute_id && row.item_id === item.id && row.unit === item.unit && ["receipt", "adjustment"].includes(row.kind) && exact(row.quantity, true) && stockMilli(row.quantity) !== 0n &&
    (row.kind !== "receipt" || stockMilli(row.quantity) > 0n) && (row.unit !== "unit" || stockMilli(row.quantity) % 1000n === 0n) &&
    typeof row.reason === "string" && row.reason.trim().length >= 3 && row.reason.length <= 240 && typeof row.actor_id === "string" && !!row.actor_id.trim() && typeof row.idempotency_key === "string" && !!row.idempotency_key.trim() && row.idempotency_key.length <= 120 && instant(row.occurred_at);
}
