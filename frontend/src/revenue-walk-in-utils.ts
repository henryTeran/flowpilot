import { certificationInstant as instant } from "./certification-utils";
import { revenueOriginalFingerprint } from "./revenue-scenario-utils";
import { validRevenueAmounts, type RevenueAmounts } from "./revenue-utils";

type Quality = "known" | "missing" | "invalid";
export type CancellationLine = { id: string; service_id: string; quantity: number; duration_minutes: number; category: string;
  unit_minor: string | null; unit_quality: Quality; total_minor: string | null; total_quality: Quality; removed_at: string | null };
export type CancellationTerms = { institute_id: string; ticket_id: string; customer_id: string | null;
  previous_status: "waiting" | "assigned" | "ready_for_checkout" | "in_checkout"; status: "cancelled"; occurred_at: string; actor_id: string | null;
  currency: "CHF" | "EUR" | null; amount_minor: string | null; amount_quality: Quality; lines: CancellationLine[];
  basis: "recorded_commercial_terms_at_cancellation"; realized_revenue: false; causal_loss_proven: false };
export type WalkInCancellation = { type: "review_cancelled_walk_in";
  evidence: { institute_id: string; ticket_id: string; event_id: number; occurred_at: string; captured_at: string;
    original: { terms: CancellationTerms; fingerprint: string } | null };
  estimated_value: { currency: "CHF" | "EUR"; amount_minor: string; basis: "recorded_cancelled_commercial_value" } | null;
  confidence: "retained_commercial_terms_not_causal_loss" | "legacy_cancellation_unpriced";
  recommended_action: "review_cancellation_and_source_terms_before_any_recovery"; action_executed: false };
export type WalkInCancellations = { window: { institute_id: string; start: string; end: string; captured_at: string };
  basis: "walk_in_cancellation_event_time"; page: { offset: number; limit: number; total: number }; opportunities: WalkInCancellation[];
  retained_terms_count: number; legacy_unpriced_count: number; retained_amounts: RevenueAmounts[]; cancelled_revenue: null; causal_loss_proven: false };
const keys = (v: unknown, names: string): v is Record<string, unknown> => !!v && typeof v === "object" && !Array.isArray(v)
  && Object.keys(v).sort().join(" ") === names.split(" ").sort().join(" ");
const count = (v: unknown): v is number => typeof v === "number" && Number.isSafeInteger(v) && v >= 0;
const id = (v: unknown): v is string => typeof v === "string" && !!v && v.trim() === v && Array.from(v).length <= 80;
const minor = (v: unknown): v is string => typeof v === "string" && /^(0|[1-9][0-9]{0,9})$/.test(v);
function amount(value: unknown, quality: unknown) { return quality === "known" ? minor(value) : ["missing", "invalid"].includes(quality as string) && value === null; }
async function original(v: unknown, institute: string, ticket: string, occurred: bigint) {
  if (!keys(v, "terms fingerprint") || typeof v.fingerprint !== "string" || !/^[a-f0-9]{64}$/.test(v.fingerprint)
    || !keys(v.terms, "institute_id ticket_id customer_id previous_status status occurred_at actor_id currency amount_minor amount_quality lines basis realized_revenue causal_loss_proven")) return false;
  const t = v.terms;
  if (t.institute_id !== institute || t.ticket_id !== ticket || !(t.customer_id === null || id(t.customer_id))
    || !["waiting", "assigned", "ready_for_checkout", "in_checkout"].includes(t.previous_status as string) || t.status !== "cancelled"
    || instant(t.occurred_at) !== occurred || !(t.actor_id === null || typeof t.actor_id === "string" && Array.from(t.actor_id).length > 0 && Array.from(t.actor_id).length <= 160)
    || ![null, "CHF", "EUR"].includes(t.currency as string | null) || !amount(t.amount_minor, t.amount_quality)
    || t.basis !== "recorded_commercial_terms_at_cancellation" || t.realized_revenue !== false || t.causal_loss_proven !== false || !Array.isArray(t.lines)) return false;
  let previous: string | undefined;
  for (const l of t.lines) {
    if (!keys(l, "id service_id quantity duration_minutes category unit_minor unit_quality total_minor total_quality removed_at")
      || !id(l.id) || !id(l.service_id) || !count(l.quantity) || l.quantity === 0 || !count(l.duration_minutes) || typeof l.category !== "string"
      || !amount(l.unit_minor, l.unit_quality) || !amount(l.total_minor, l.total_quality)
      || !(l.removed_at === null || instant(l.removed_at) !== undefined && instant(l.removed_at)! <= occurred)
      || previous !== undefined && previous >= l.id) return false;
    previous = l.id;
  }
  return await revenueOriginalFingerprint(t) === v.fingerprint;
}
export async function validWalkInCancellations(v: unknown, institute: string, period: { start: string; end: string }, offset: number): Promise<boolean> {
  if (!keys(v, "window basis page opportunities retained_terms_count legacy_unpriced_count retained_amounts cancelled_revenue causal_loss_proven")
    || !keys(v.window, "institute_id start end captured_at") || v.window.institute_id !== institute || v.basis !== "walk_in_cancellation_event_time"
    || v.cancelled_revenue !== null || v.causal_loss_proven !== false || !keys(v.page, "offset limit total")
    || v.page.offset !== offset || v.page.limit !== 20 || !count(v.page.total) || !count(v.retained_terms_count) || !count(v.legacy_unpriced_count)
    || BigInt(v.retained_terms_count) + BigInt(v.legacy_unpriced_count) !== BigInt(v.page.total)
    || !Array.isArray(v.opportunities) || v.opportunities.length !== Math.min(20, Math.max(0, v.page.total-offset))
    || !Array.isArray(v.retained_amounts) || !v.retained_amounts.every(validRevenueAmounts)
    || new Set(v.retained_amounts.map(g => g.currency)).size !== v.retained_amounts.length
    || v.retained_amounts.reduce((n,g) => n+BigInt(g.source_count), 0n) !== BigInt(v.retained_terms_count)) return false;
  const start = instant(v.window.start), end = instant(v.window.end), captured = instant(v.window.captured_at);
  if (start === undefined || end === undefined || captured === undefined || start >= end || end > captured
    || start !== instant(period.start) || end !== instant(period.end)) return false;
  const events = new Set<number>(), tickets = new Set<string>(); let previous: [bigint, number] | undefined, retained = 0, legacy = 0;
  const returned = new Map<string | null, { known: number; missing: number; invalid: number; gross: bigint }>();
  for (const o of v.opportunities) {
    if (!keys(o, "type evidence estimated_value confidence recommended_action action_executed") || o.type !== "review_cancelled_walk_in"
      || o.action_executed !== false || o.recommended_action !== "review_cancellation_and_source_terms_before_any_recovery"
      || !keys(o.evidence, "institute_id ticket_id event_id occurred_at captured_at original")) return false;
    const e = o.evidence, at = instant(e.occurred_at);
    if (e.institute_id !== institute || !id(e.ticket_id) || !count(e.event_id) || !e.event_id || at === undefined || at < start || at >= end
      || instant(e.captured_at) !== captured || events.has(e.event_id) || tickets.has(e.ticket_id)
      || previous && (at < previous[0] || at === previous[0] && e.event_id <= previous[1])) return false;
    events.add(e.event_id); tickets.add(e.ticket_id); previous = [at, e.event_id];
    if (e.original === null) { legacy++; if (o.estimated_value !== null || o.confidence !== "legacy_cancellation_unpriced") return false; }
    else {
      retained++; if (!await original(e.original, institute, e.ticket_id, at) || o.confidence !== "retained_commercial_terms_not_causal_loss") return false;
      const t = (e.original as NonNullable<WalkInCancellation["evidence"]["original"]>).terms;
      if (t.currency !== null && t.amount_quality === "known") {
        if (!keys(o.estimated_value, "currency amount_minor basis") || o.estimated_value.currency !== t.currency || o.estimated_value.amount_minor !== t.amount_minor
          || o.estimated_value.basis !== "recorded_cancelled_commercial_value") return false;
      } else if (o.estimated_value !== null) return false;
      const g = returned.get(t.currency) || { known: 0, missing: 0, invalid: 0, gross: 0n };
      g[t.amount_quality]++; if (t.amount_quality === "known") g.gross += BigInt(t.amount_minor!); returned.set(t.currency, g);
    }
  }
  if (retained > v.retained_terms_count || legacy > v.legacy_unpriced_count) return false;
  for (const [currency, r] of returned) {
    const g = v.retained_amounts.find(g => g.currency === currency);
    if (!g || r.known > g.known_amount_count || r.missing > g.missing_amount_count || r.invalid > g.invalid_amount_count || r.gross > BigInt(g.known_gross_minor)
      || BigInt(g.known_gross_minor)-r.gross > BigInt(g.known_amount_count-r.known)*9999999999n) return false;
    if (offset === 0 && v.page.total <= 20 && (r.known !== g.known_amount_count || r.missing !== g.missing_amount_count || r.invalid !== g.invalid_amount_count || r.gross !== BigInt(g.known_gross_minor))) return false;
  }
  return true;
}
