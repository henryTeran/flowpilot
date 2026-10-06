import { validOutlookItems, type OutlookItem } from "./outlook-utils";
import { stockMilli } from "./inventory-utils";
export type Period = { starts_at: string; ends_at: string };
export type PlannedRequest = Period & { include_waiting_queue: boolean };
export type ObservedRequest = Period & { observed_starts_at: string; observed_ends_at: string };
type Common = Period & { institute_id: string; generated_at: string; effective_starts_at: string; limit: number; offset: number; coverage: string };
export type Planned = Common & { source: string; norm_basis: string; queue_timing: string; include_waiting_queue: boolean; appointment_count: number; waiting_line_count: number; service_quantity: number; missing_norm_quantity: number; disabled_norm_quantity: number; items: OutlookItem[] };
export type ObservedItem = Omit<OutlookItem, "known_demand" | "complete_demand" | "known_demand_shortfall"> & { observed_quantity: string; recorded_pace_projection: string; complete_pace_projection: string | null; recorded_projection_shortfall: string };
export type Observed = Common & ObservedRequest & { source: string; assumption: string; completed_executions: number; captured_bases: number; signed_confirmations: number; pending_bases: number; legacy_completed_executions: number; undated_completed_executions: number; items: ObservedItem[] };
// Preserve server microseconds when validating clipping and pace arithmetic.
export function instantMicros(value: unknown): bigint | undefined {
  if (typeof value !== "string") return;
  const match = /^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d{1,6}))?(Z|[+-]\d{2}:\d{2})$/.exec(value);
  if (!match || Number(match[1].slice(0, 4)) === 0) return;
  const civil = Date.parse(match[1] + "Z"), epoch = Date.parse(match[1] + match[3]);
  if (!Number.isFinite(epoch) || !Number.isFinite(civil) || new Date(civil).toISOString().slice(0, 19) !== match[1]) return;
  return BigInt(epoch) * 1000n + BigInt((match[2] || "").padEnd(6, "0"));
}
const count = (v: unknown): v is number => Number.isSafeInteger(v) && (v as number) >= 0;
export function validPeriod(p: Period): boolean {
  const start = instantMicros(p.starts_at), end = instantMicros(p.ends_at);
  return start !== undefined && end !== undefined && end > start && end - start <= 366n * 86400000000n;
}
function common(s: Common, institute: string, offset: number, request: Period): boolean {
  if (!s || s.institute_id !== institute || s.limit !== 20 || s.offset !== offset || !validPeriod(request)) return false;
  const generated = instantMicros(s.generated_at), start = instantMicros(s.starts_at), end = instantMicros(s.ends_at), effective = instantMicros(s.effective_starts_at);
  return generated !== undefined && start === instantMicros(request.starts_at) && end === instantMicros(request.ends_at) && effective !== undefined && effective === (start! > generated ? start! : generated) && end! > effective;
}
export function validPlanned(v: unknown, institute: string, offset: number, request: PlannedRequest): v is Planned {
  const s = v as Planned;
  if (!common(s, institute, offset, request) || typeof request.include_waiting_queue !== "boolean" || s.include_waiting_queue !== request.include_waiting_queue || s.source !== "recorded_upcoming_demand" || s.norm_basis !== "provisional_current_at_read" || s.queue_timing !== "unscheduled_at_read" || ![s.appointment_count, s.waiting_line_count, s.service_quantity, s.missing_norm_quantity, s.disabled_norm_quantity].every(count)) return false;
  if (!request.include_waiting_queue && s.waiting_line_count !== 0 || s.service_quantity < s.appointment_count + s.waiting_line_count || s.missing_norm_quantity + s.disabled_norm_quantity > s.service_quantity) return false;
  if (!s.waiting_line_count && s.service_quantity !== s.appointment_count) return false;
  const complete = s.missing_norm_quantity === 0;
  return s.coverage === (complete ? "complete_recorded_norms" : "partial_recorded_norms") && validOutlookItems(s.items, complete, s.service_quantity === s.missing_norm_quantity + s.disabled_norm_quantity) && s.items.every(row => stockMilli(row.known_demand) <= 999999999999999n * BigInt(s.service_quantity - s.missing_norm_quantity - s.disabled_norm_quantity));
}
export function validObserved(v: unknown, institute: string, offset: number, request: ObservedRequest): v is Observed {
  const s = v as Observed;
  if (!common(s, institute, offset, request) || !validPeriod({ starts_at: request.observed_starts_at, ends_at: request.observed_ends_at }) || instantMicros(s.observed_starts_at) !== instantMicros(request.observed_starts_at) || instantMicros(s.observed_ends_at) !== instantMicros(request.observed_ends_at) || s.source !== "signed_completed_service_usage" || s.assumption !== "constant_elapsed_time_pace") return false;
  const observedEnd = instantMicros(s.observed_ends_at)!, generated = instantMicros(s.generated_at)!;
  if (observedEnd > generated || ![s.completed_executions, s.captured_bases, s.signed_confirmations, s.pending_bases, s.legacy_completed_executions, s.undated_completed_executions].every(count) || s.captured_bases !== s.signed_confirmations + s.pending_bases || s.legacy_completed_executions > s.completed_executions || s.captured_bases < s.completed_executions - s.legacy_completed_executions || (!s.completed_executions && s.captured_bases !== 0)) return false;
  if (s.completed_executions === s.legacy_completed_executions && s.captured_bases !== 0) return false;
  const complete = s.completed_executions > 0 && !s.pending_bases && !s.legacy_completed_executions && !s.undated_completed_executions;
  const coverage = !s.completed_executions ? "no_completed_sample" : complete ? "complete_signed_sample" : "partial_signed_sample";
  if (s.coverage !== coverage || !Array.isArray(s.items)) return false;
  const rows = s.items.map(row => row && ({ ...row, known_demand: row.recorded_pace_projection, complete_demand: row.complete_pace_projection, known_demand_shortfall: row.recorded_projection_shortfall }));
  if (!validOutlookItems(rows, complete, !s.signed_confirmations)) return false;
  const duration = instantMicros(s.observed_ends_at)! - instantMicros(s.observed_starts_at)!, future = instantMicros(s.ends_at)! - instantMicros(s.effective_starts_at)!;
  return s.items.every(row => {
    if (typeof row.observed_quantity !== "string" || !/^(0|[1-9]\d{0,63})\.\d{3}$/.test(row.observed_quantity)) return false;
    const measured = stockMilli(row.observed_quantity), quantum = row.unit === "unit" ? 1000n : 1n;
    if (measured % quantum || measured > 999999999999999n * BigInt(s.signed_confirmations)) return false;
    return stockMilli(row.recorded_pace_projection) === ((measured * future + duration * quantum - 1n) / (duration * quantum)) * quantum;
  });
}
