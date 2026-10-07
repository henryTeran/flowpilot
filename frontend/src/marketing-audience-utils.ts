import { certificationInstant as instant } from "./certification-utils";
import { validSegmentProfile, type SegmentProfile } from "./crm-segment-utils";
import { validLifecycleOriginal, type LifecycleOriginal } from "./crm-lifecycle-utils";

export const marketingSegments = ["NEW", "ACTIVE", "LOYAL", "VIP", "AT_RISK", "DORMANT"] as const;
export type MarketingSegment = typeof marketingSegments[number];
export type AudienceRequest = { segments: MarketingSegment[]; channel: "email" | "sms" | "push"; reason: string; idempotency_key: string };
export type AudienceOriginal = { id: string; institute_id: string; actor_id: string; captured_at: string;
  request: AudienceRequest; summary: { page_count: number; customer_count: number; selected_count: number; eligible_count: number };
  complete_registered_cohort: true; delivery_authorized: false };
export type AudienceObservation = { institute_id: string; captured_at: string;
  selection: { segments: MarketingSegment[]; channel: AudienceRequest["channel"]; after: string | null };
  next_after: string | null; items: { customer_id: string; profile: SegmentProfile; declaration: LifecycleOriginal | null;
    selected_segment: boolean; marketing_permission: "granted" | "refused" | "unknown" | "unsupported_channel" | "future_declaration";
    eligible_by_recorded_permission: boolean; delivery_authorized: false }[];
  complete_institute_audience: false; delivery_authorized: false };
export type RetainedAudiencePage = { capture_id: string; page_index: number; observation: AudienceObservation };
export type AudienceCatalog = { institute_id: string; total: number; offset: number; limit: number; items: AudienceOriginal[] };
const text = (v: unknown, max = 80): v is string => typeof v === "string" && !!v.trim() && v.trim() === v && Array.from(v).length <= max;
const count = (v: unknown): v is number => Number.isSafeInteger(v) && (v as number) >= 0;
const keys = (v: unknown, expected: string[]) => !!v && typeof v === "object" && !Array.isArray(v)
  && Object.keys(v).length === expected.length && expected.every(k => Object.prototype.hasOwnProperty.call(v, k));
const segments = (v: unknown): v is MarketingSegment[] => Array.isArray(v) && v.length > 0
  && v.every(s => marketingSegments.includes(s)) && new Set(v).size === v.length;
const sameSegments = (a: MarketingSegment[], b: MarketingSegment[]) => a.length === b.length && a.every((s, i) => s === b[i]);
export function validAudienceRequest(v: unknown): v is AudienceRequest {
  const r = v as AudienceRequest;
  return keys(r, ["segments", "channel", "reason", "idempotency_key"]) && segments(r.segments)
    && ["email", "sms", "push"].includes(r.channel) && text(r.reason, 240) && Array.from(r.reason).length >= 3 && text(r.idempotency_key, 120);
}
export function validAudienceOriginal(v: unknown, institute: string): v is AudienceOriginal {
  const r = v as AudienceOriginal, s = r?.summary;
  return keys(r, ["id", "institute_id", "actor_id", "captured_at", "request", "summary", "complete_registered_cohort", "delivery_authorized"])
    && text(r.id) && text(r.institute_id) && r.institute_id === institute && text(r.actor_id, 160) && instant(r.captured_at) !== undefined
    && validAudienceRequest(r.request) && keys(s, ["page_count", "customer_count", "selected_count", "eligible_count"])
    && count(s.customer_count) && count(s.selected_count) && count(s.eligible_count) && count(s.page_count)
    && s.page_count === Math.max(1, Math.ceil(s.customer_count / 50)) && s.eligible_count <= s.selected_count && s.selected_count <= s.customer_count
    && r.complete_registered_cohort === true && r.delivery_authorized === false;
}
export function matchesAudienceReceipt(r: AudienceOriginal, request: AudienceRequest, actor: string): boolean {
  return r.actor_id === actor && sameSegments(r.request.segments, request.segments) && r.request.channel === request.channel
    && r.request.reason === request.reason && r.request.idempotency_key === request.idempotency_key;
}
export function sameAudienceOriginal(a: AudienceOriginal, b: AudienceOriginal): boolean {
  return a.id === b.id && a.institute_id === b.institute_id && instant(a.captured_at) === instant(b.captured_at)
    && matchesAudienceReceipt(a, b.request, b.actor_id) && a.summary.page_count === b.summary.page_count
    && a.summary.customer_count === b.summary.customer_count && a.summary.selected_count === b.summary.selected_count && a.summary.eligible_count === b.summary.eligible_count;
}
export function validAudienceObservation(v: unknown, institute: string): v is AudienceObservation {
  const p = v as AudienceObservation;
  if (!keys(p, ["institute_id", "captured_at", "selection", "next_after", "items", "complete_institute_audience", "delivery_authorized"])
    || p.institute_id !== institute || instant(p.captured_at) === undefined || p.delivery_authorized !== false || p.complete_institute_audience !== false
    || !keys(p.selection, ["segments", "channel", "after"]) || !segments(p.selection.segments) || !["email", "sms", "push"].includes(p.selection.channel)
    || !(p.selection.after === null || text(p.selection.after)) || !Array.isArray(p.items) || p.items.length > 50) return false;
  let previous = p.selection.after || "";
  for (const item of p.items) {
    if (!keys(item, ["customer_id", "profile", "declaration", "selected_segment", "marketing_permission", "eligible_by_recorded_permission", "delivery_authorized"])
      || !text(item.customer_id) || item.customer_id <= previous || item.delivery_authorized !== false
      || !validSegmentProfile(item.profile, institute, item.customer_id) || instant(item.profile.captured_at) !== instant(p.captured_at)
      || item.declaration !== null && !validLifecycleOriginal(item.declaration, institute, item.customer_id)) return false;
    previous = item.customer_id;
    const selected = item.profile.segment?.state != null && p.selection.segments.includes(item.profile.segment.state);
    const d = item.declaration;
    const permission = p.selection.channel === "push" ? "unsupported_channel" : d === null ? "unknown"
      : instant(d.created_at)! > instant(p.captured_at)! ? "future_declaration"
      : d.declaration.communications.find(c => c.channel === p.selection.channel && c.purpose === "marketing")!.permission;
    if (item.selected_segment !== selected || item.marketing_permission !== permission || item.eligible_by_recorded_permission !== (selected && permission === "granted")) return false;
  }
  return p.next_after === null || p.items.length === 50 && p.next_after === previous;
}
export function validRetainedAudiencePage(v: unknown, original: AudienceOriginal, index: number, after: string | null): v is RetainedAudiencePage {
  const p = v as RetainedAudiencePage;
  return keys(p, ["capture_id", "page_index", "observation"]) && count(index) && index < original.summary.page_count
    && p.capture_id === original.id && p.page_index === index && validAudienceObservation(p.observation, original.institute_id)
    && instant(p.observation.captured_at) === instant(original.captured_at) && p.observation.selection.after === after
    && (index !== 0 || after === null) && (index === 0 || text(after))
    && sameSegments(p.observation.selection.segments, original.request.segments) && p.observation.selection.channel === original.request.channel
    && p.observation.items.length === (index < original.summary.page_count - 1 ? 50 : original.summary.customer_count - 50 * index)
    && (index === original.summary.page_count - 1 ? p.observation.next_after === null : p.observation.next_after !== null);
}
export function validAudienceCatalog(v: unknown, institute: string, offset: number, limit: number): v is AudienceCatalog {
  const p = v as AudienceCatalog;
  return keys(p, ["institute_id", "total", "offset", "limit", "items"]) && p.institute_id === institute
    && count(p.total) && count(offset) && count(limit) && limit >= 1 && limit <= 50 && p.offset === offset && p.limit === limit
    && Array.isArray(p.items) && p.items.length === Math.min(limit, Math.max(0, p.total - offset))
    && p.items.every(r => validAudienceOriginal(r, institute)) && new Set(p.items.map(r => r.id)).size === p.items.length
    && p.items.every((r, i) => i === 0 || instant(p.items[i - 1].captured_at)! > instant(r.captured_at)!
      || instant(p.items[i - 1].captured_at) === instant(r.captured_at) && p.items[i - 1].id < r.id);
}
