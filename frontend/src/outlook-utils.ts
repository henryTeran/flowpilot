import { stockMilli, stockUnits, stockCategories } from "./inventory-utils";
import { purchaseText, purchaseReference } from "./order-utils";
export type Scenario = { starts_at: string; ends_at: string; demands: Array<{ service_id: string; recipe_id: string | null; quantity: number }> };
export type OutlookItem = { item_id: string; item_sku: string; item_name: string; category: keyof typeof stockCategories; unit: keyof typeof stockUnits; on_hand: string; threshold: string; at_or_below_threshold: boolean; threshold_shortfall: string; pending_order_quantity: string; known_demand: string; complete_demand: string | null; known_demand_shortfall: string; conditional_shortfall_after_all_orders: string };
export type Outlook = { institute_id: string; generated_at: string; starts_at: string | null; ends_at: string | null; source: string; coverage: string; demands: Array<Scenario["demands"][number] & { service_name: string; recipe_revision: number | null; state: string }>; limit: number; offset: number; items: OutlookItem[] };
const instant = (v: unknown): v is string => typeof v === "string" && /(?:Z|[+-]\d{2}:\d{2})$/.test(v) && Number.isFinite(Date.parse(v));
const exact = (v: unknown, unit: string, physical = false): v is string => typeof v === "string" && /^(0|[1-9]\d{0,19})\.\d{3}$/.test(v) && (!physical || stockMilli(v) <= 999999999999999n) && (unit !== "unit" || stockMilli(v) % 1000n === 0n);
export function validScenario(v: unknown): v is Scenario {
  const s = v as Scenario;
  return !!s && instant(s.starts_at) && instant(s.ends_at) && Date.parse(s.ends_at) > Date.parse(s.starts_at) && Date.parse(s.ends_at) - Date.parse(s.starts_at) <= 366 * 86400000 && Array.isArray(s.demands) && s.demands.length > 0 && s.demands.length <= 50 && s.demands.every(d => !!d && purchaseText(d.service_id, 80) && (d.recipe_id === null || purchaseText(d.recipe_id, 80)) && Number.isInteger(d.quantity) && d.quantity >= 1 && d.quantity <= 100000) && new Set(s.demands.map(d => d.service_id)).size === s.demands.length;
}
export function validOutlook(v: unknown, institute: string, offset: number, scenario?: Scenario): v is Outlook {
  const s = v as Outlook;
  if (!s || s.institute_id !== institute || s.limit !== 20 || s.offset !== offset || !instant(s.generated_at) || !Array.isArray(s.items) || s.items.length > 20 || !Array.isArray(s.demands)) return false;
  const complete = !!scenario && scenario.demands.every(d => d.recipe_id !== null);
  if (scenario) {
    if (!validScenario(scenario) || !instant(s.starts_at) || !instant(s.ends_at) || Date.parse(s.starts_at) !== Date.parse(scenario.starts_at) || Date.parse(s.ends_at) !== Date.parse(scenario.ends_at) || s.source !== "explicit_service_volume_scenario" || s.coverage !== (complete ? "complete_selected_norms" : "partial_selected_norms") || s.demands.length !== scenario.demands.length || new Set(s.demands.map(d => d?.service_id)).size !== s.demands.length) return false;
    if (!s.demands.every(d => { const chosen = scenario.demands.find(row => row.service_id === d?.service_id); return !!chosen && d.recipe_id === chosen.recipe_id && d.quantity === chosen.quantity && purchaseText(d.service_name, 160) && (chosen.recipe_id === null ? d.state === "missing_selected_norm" && d.recipe_revision === null : ["enabled", "disabled"].includes(d.state) && Number.isInteger(d.recipe_revision) && d.recipe_revision! > 0); })) return false;
  } else if (s.source !== "recorded_stock" || s.coverage !== "not_applicable" || s.starts_at !== null || s.ends_at !== null || s.demands.length) return false;
  return s.items.every(row => {
    if (!row || !purchaseText(row.item_id, 80) || !purchaseReference(row.item_sku) || !purchaseText(row.item_name, 120) || !Object.prototype.hasOwnProperty.call(stockUnits, row.unit) || !Object.prototype.hasOwnProperty.call(stockCategories, row.category) || !exact(row.on_hand, row.unit, true) || !exact(row.threshold, row.unit, true) || ![row.threshold_shortfall, row.pending_order_quantity, row.known_demand, row.known_demand_shortfall, row.conditional_shortfall_after_all_orders].every(q => exact(q, row.unit))) return false;
    const hand = stockMilli(row.on_hand), threshold = stockMilli(row.threshold), demand = stockMilli(row.known_demand), pending = stockMilli(row.pending_order_quantity), max = (v: bigint) => v < 0n ? 0n : v;
    return row.at_or_below_threshold === (hand <= threshold) && stockMilli(row.threshold_shortfall) === max(threshold - hand) && stockMilli(row.known_demand_shortfall) === max(demand + threshold - hand) && stockMilli(row.conditional_shortfall_after_all_orders) === max(demand + threshold - hand - pending) && (complete ? row.complete_demand === row.known_demand : row.complete_demand === null) && (scenario || row.known_demand === "0.000");
  }) && new Set(s.items.map(row => row.item_id)).size === s.items.length && new Set(s.items.map(row => row.item_sku)).size === s.items.length;
}
// Resolve a civil date in the institute's zone; reject skipped/ambiguous midnight.
export function instituteMidnight(date: string, zone: string): string | undefined {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return;
  const target = Date.parse(`${date}T00:00:00Z`);
  if (!Number.isFinite(target) || new Date(target).toISOString().slice(0, 10) !== date) return;
  try {
    const formatter = new Intl.DateTimeFormat("en-GB", { timeZone: zone, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23" });
    const civil = (value: number) => { const p = Object.fromEntries(formatter.formatToParts(new Date(value)).map(p => [p.type, p.value])); return `${p.year.padStart(4, "0")}-${p.month}-${p.day}T${p.hour}:${p.minute}:${p.second}Z`; };
    const candidates = new Set<number>();
    for (let hour = -36; hour <= 36; hour++) { const sample = target + hour * 3600000, offset = Date.parse(civil(sample)) - sample, value = target - offset; if (civil(value) === `${date}T00:00:00Z`) candidates.add(value); }
    if (candidates.size === 1) return new Date([...candidates][0]).toISOString();
  } catch { return; }
}
