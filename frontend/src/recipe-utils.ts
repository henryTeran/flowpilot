import { stockMilli, stockQuantity, stockUnits, type StockItem } from "./inventory-utils";
export type RecipeEntry = { item_id: string; quantity: string; unit: StockItem["unit"] };
export type Recipe = { id: string; institute_id: string; service_id: string; revision: number; base_revision: number; enabled: boolean; entries: RecipeEntry[]; reason: string; actor_id: string; idempotency_key: string; created_at: string };
export type RecipeIntent = { service_name?: string; base_revision: number; enabled: boolean; entries: Array<RecipeEntry & { name: string; sku: string }>; reason: string; idempotency_key: string };
const id = (value: unknown) => typeof value === "string" && !!value.trim() && value === value.trim() && value.length <= 80;
export function validEntries(entries: unknown): entries is RecipeEntry[] {
  return Array.isArray(entries) && entries.length <= 50 && entries.every(row => !!row && id(row.item_id) && Object.prototype.hasOwnProperty.call(stockUnits, row.unit) && typeof row.quantity === "string" && stockQuantity(row.quantity, row.unit) === row.quantity && stockMilli(row.quantity) > 0n) && new Set(entries.map(row => row.item_id)).size === entries.length;
}
export function validRecipe(value: unknown, institute: string, service: string): value is Recipe {
  const row = value as Recipe;
  return !!row && id(row.id) && row.institute_id === institute && row.service_id === service && Number.isInteger(row.revision) && row.revision >= 1 && row.revision <= 1000000000 && row.base_revision === row.revision - 1 && typeof row.enabled === "boolean" && validEntries(row.entries) && row.enabled === !!row.entries.length && typeof row.reason === "string" && row.reason.trim().length >= 3 && row.reason.length <= 240 && typeof row.actor_id === "string" && !!row.actor_id.trim() && row.actor_id.length <= 160 && typeof row.idempotency_key === "string" && !!row.idempotency_key.trim() && row.idempotency_key.length <= 120 && typeof row.created_at === "string" && /(?:Z|[+-]\d{2}:\d{2})$/.test(row.created_at) && Number.isFinite(Date.parse(row.created_at));
}
export function validRecipeIntent(row: RecipeIntent): boolean {
  return !!row && (row.service_name === undefined || (typeof row.service_name === "string" && !!row.service_name.trim() && row.service_name.length <= 160)) && Number.isInteger(row.base_revision) && row.base_revision >= 0 && row.base_revision < 1000000000 && typeof row.enabled === "boolean" && validEntries(row.entries) && row.enabled === !!row.entries.length && row.entries.every(entry => typeof entry.name === "string" && !!entry.name.trim() && entry.name.length <= 120 && typeof entry.sku === "string" && /^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$/.test(entry.sku)) && typeof row.reason === "string" && row.reason.trim().length >= 3 && row.reason.length <= 240 && typeof row.idempotency_key === "string" && !!row.idempotency_key.trim() && row.idempotency_key.length <= 120;
}
export const recipeTerms = (entries: RecipeEntry[]) => JSON.stringify(entries.map(row => [row.item_id, row.quantity, row.unit]).sort((a, b) => a[0].localeCompare(b[0])));
export function matchesRecipe(row: Recipe, intent: RecipeIntent, actor: string) {
  return row.base_revision === intent.base_revision && row.enabled === intent.enabled && row.reason === intent.reason && row.idempotency_key === intent.idempotency_key && row.actor_id === actor && recipeTerms(row.entries) === recipeTerms(intent.entries);
}
