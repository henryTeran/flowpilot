import { certificationInstant as instant } from "./certification-utils";
export type RevenueSlot = { institute_id: string; service_id: string; captured_at: string; horizon_end: string;
  opportunity: { type: "review_projected_walk_in_slot";
    evidence: { institute_id: string; captured_at: string; horizon_end: string; service_id: string; duration_minutes: number;
      required_skills: string[]; resource_needs: { kind: "room" | "equipment" | "bed" | "chair" | "device"; capability: string; quantity: number }[];
      prior_queue_count: number; unprojectable_prior_queue_count: number; employee_id: string; projected_start: string; projected_end: string };
    estimated_value: null; confidence: "conditional_current_queue_projection";
    recommended_action: "review_opening_hours_and_revalidate_capacity_before_assignment"; capacity_reserved: false; action_executed: false } | null;
  unavailable_reason: "resource_configuration_missing" | "capacity_unknown" | "outside_horizon" | null };
const keys = (v: unknown, names: string): v is Record<string, unknown> => !!v && typeof v === "object" && !Array.isArray(v)
  && Object.keys(v).sort().join(" ") === names.split(" ").sort().join(" ");
const count = (v: unknown): v is number => typeof v === "number" && Number.isSafeInteger(v) && v >= 0;
const id = (v: unknown): v is string => typeof v === "string" && !!v && v.trim() === v && Array.from(v).length <= 80;
export function validRevenueSlot(v: unknown, institute: string, service: string, horizon: string): v is RevenueSlot {
  if (!keys(v, "institute_id service_id captured_at horizon_end opportunity unavailable_reason") || v.institute_id !== institute || v.service_id !== service) return false;
  const capture = instant(v.captured_at), end = instant(v.horizon_end);
  if (capture === undefined || end === undefined || capture >= end || end !== instant(horizon)) return false;
  if (v.opportunity === null) return ["resource_configuration_missing", "capacity_unknown", "outside_horizon"].includes(v.unavailable_reason as string);
  const o = v.opportunity;
  if (v.unavailable_reason !== null || !keys(o, "type evidence estimated_value confidence recommended_action capacity_reserved action_executed")
    || o.type !== "review_projected_walk_in_slot" || o.estimated_value !== null || o.confidence !== "conditional_current_queue_projection"
    || o.recommended_action !== "review_opening_hours_and_revalidate_capacity_before_assignment" || o.capacity_reserved !== false || o.action_executed !== false
    || !keys(o.evidence, "institute_id captured_at horizon_end service_id duration_minutes required_skills resource_needs prior_queue_count unprojectable_prior_queue_count employee_id projected_start projected_end")) return false;
  const e = o.evidence, first = instant(e.projected_start), last = instant(e.projected_end);
  if (e.institute_id !== institute || e.service_id !== service || instant(e.captured_at) !== capture || instant(e.horizon_end) !== end || !id(e.employee_id)
    || !count(e.duration_minutes) || !e.duration_minutes || first === undefined || last === undefined || first < capture || last > end
    || last-first !== BigInt(e.duration_minutes)*60_000_000n || !count(e.prior_queue_count) || !count(e.unprojectable_prior_queue_count)
    || e.unprojectable_prior_queue_count > e.prior_queue_count || !Array.isArray(e.required_skills) || !Array.isArray(e.resource_needs)) return false;
  let previous: string | undefined;
  for (const skill of e.required_skills) { if (typeof skill !== "string" || previous !== undefined && skill <= previous) return false; previous = skill; }
  const seen = new Set<string>();
  for (const need of e.resource_needs) {
    if (!keys(need, "kind capability quantity") || !["room", "equipment", "bed", "chair", "device"].includes(need.kind as string)
      || typeof need.capability !== "string" || !count(need.quantity) || need.quantity < 1 || need.quantity > 10) return false;
    const identity = JSON.stringify([need.kind,need.capability]); if (seen.has(identity)) return false; seen.add(identity);
  }
  return true;
}
