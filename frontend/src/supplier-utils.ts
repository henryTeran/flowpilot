export type SupplierIntent = { reference: string; name: string; reason: string; idempotency_key: string };
export type Supplier = SupplierIntent & { id: string; institute_id: string; actor_id: string; created_at: string };
const text = (value: unknown, max: number, min = 1): value is string => typeof value === "string" && value === value.trim() && value.length >= min && value.length <= max;
export function validSupplierIntent(value: unknown): value is SupplierIntent {
  const row = value as SupplierIntent;
  return !!row && text(row.reference, 80) && /^[A-Za-z0-9][A-Za-z0-9._-]*$/.test(row.reference) && text(row.name, 120) && text(row.reason, 240, 3) && text(row.idempotency_key, 120);
}
export function validSupplier(value: unknown, institute: string): value is Supplier {
  const row = value as Supplier;
  return validSupplierIntent(row) && row.institute_id === institute && text(row.id, 80) && text(row.actor_id, 160) && typeof row.created_at === "string" && /(?:Z|[+-]\d{2}:\d{2})$/.test(row.created_at) && Number.isFinite(Date.parse(row.created_at));
}
export const matchesSupplier = (row: Supplier, intent: SupplierIntent, actor: string) => row.actor_id === actor && row.reference === intent.reference && row.name === intent.name && row.reason === intent.reason && row.idempotency_key === intent.idempotency_key;
