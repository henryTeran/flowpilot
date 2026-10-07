import { certificationInstant as instant } from "./certification-utils";
import { crmUnsigned, type BillingRatio, type BillingWindow } from "./crm-billing-utils";
export type CareEpisode = { ticket_id: string; started_at: string; completed_at: string; execution_count: number; service_ids: string[] };
export type ReturnGap = { previous_ticket_id: string; next_ticket_id: string; gap_us: string | null; quality: "known" | "overlapping_episodes" };
export type ReturnRead = { complete_execution_coverage: false; complete_service_coverage: false;
  summary: { window: BillingWindow; basis: "recorded_completed_ticket_care"; execution_count: number; episode_count: number;
    known_gap_count: number; overlapping_gap_count: number; known_gap_total_us: string; average_return_gap_us: BillingRatio | null;
    complete_customer_history: false; inferred_booking_credit: false };
  diagnostics: { unlinked_ticket: number; invalid_owner_or_service: number; invalid_actual_times: number };
  page: { offset: number; limit: number; total: number }; episodes: CareEpisode[]; gaps: ReturnGap[] };
const count = (v: unknown): v is number => Number.isSafeInteger(v) && (v as number) >= 0;
const id = (v: unknown): v is string => typeof v === "string" && !!v && v.trim() === v && v.length <= 80;
const diagnosticKeys = ["unlinked_ticket", "invalid_owner_or_service", "invalid_actual_times"] as const;

export function validReturnRead(value: unknown, institute: string, customer: string, startText: string, endText: string,
  offset = 0, limit = 20): value is ReturnRead {
  const r = value as ReturnRead, start = instant(startText), end = instant(endText);
  if (!r || !r.summary || !r.summary.window || !r.page || !r.diagnostics || !Array.isArray(r.episodes) || !Array.isArray(r.gaps)
    || r.complete_execution_coverage !== false || r.complete_service_coverage !== false || start === undefined || end === undefined || start >= end) return false;
  const s = r.summary, w = s.window, captured = instant(w.captured_at);
  if (w.institute_id !== institute || w.customer_id !== customer || instant(w.start) !== start || instant(w.end) !== end
    || captured === undefined || captured < end || s.basis !== "recorded_completed_ticket_care" || s.complete_customer_history !== false
    || s.inferred_booking_credit !== false || !count(s.execution_count) || !count(s.episode_count) || !count(s.known_gap_count)
    || !count(s.overlapping_gap_count) || s.execution_count < s.episode_count || s.episode_count === 0 && s.execution_count !== 0) return false;
  if (BigInt(s.known_gap_count)+BigInt(s.overlapping_gap_count) !== BigInt(Math.max(s.episode_count-1, 0))) return false;
  const total = crmUnsigned(s.known_gap_total_us);
  // Positive gaps between ordered episodes are disjoint within the observed window.
  if (total === undefined || total > end-start || s.known_gap_count === 0 && total !== 0n) return false;
  if (Object.keys(r.diagnostics).length !== 3 || !diagnosticKeys.every(k => Object.prototype.hasOwnProperty.call(r.diagnostics,k) && count(r.diagnostics[k]))) return false;
  const mean = s.average_return_gap_us;
  if (s.known_gap_count && !s.overlapping_gap_count && !diagnosticKeys.some(k => r.diagnostics[k])) {
    if (!mean || crmUnsigned(mean.numerator) !== total || crmUnsigned(mean.denominator) !== BigInt(s.known_gap_count)) return false;
  } else if (mean !== null) return false;
  if (!count(offset) || !count(limit) || limit < 1 || limit > 50 || r.page.offset !== offset || r.page.limit !== limit
    || r.page.total !== s.episode_count || r.episodes.length !== Math.min(limit, Math.max(s.episode_count-offset, 0))) return false;
  const tickets = new Set<string>(); let executions = 0n, priorStart: bigint | undefined, priorEnd: bigint | undefined;
  for (const e of r.episodes) {
    const began = instant(e?.started_at), completed = instant(e?.completed_at);
    if (!e || !id(e.ticket_id) || tickets.has(e.ticket_id) || began === undefined || completed === undefined || began >= completed
      || completed < start || completed >= end || !count(e.execution_count) || e.execution_count < 1 || !Array.isArray(e.service_ids)
      || !e.service_ids.length || !e.service_ids.every(id) || new Set(e.service_ids).size !== e.service_ids.length
      || e.service_ids.length > e.execution_count || priorStart !== undefined && (began < priorStart || began === priorStart && completed < priorEnd!)) return false;
    tickets.add(e.ticket_id); executions += BigInt(e.execution_count); priorStart = began; priorEnd = completed;
  }
  if (executions > BigInt(s.execution_count) || offset === 0 && s.episode_count <= limit && executions !== BigInt(s.execution_count)) return false;
  const first = offset === 0 && r.episodes.length ? 1 : 0;
  if (r.gaps.length !== r.episodes.length-first) return false;
  let known = 0n, overlapping = 0n, visibleTotal = 0n;
  for (let i = 0; i < r.gaps.length; i++) {
    const g = r.gaps[i], next = r.episodes[i+first], previous = r.episodes[i+first-1];
    if (!g || !id(g.previous_ticket_id) || g.next_ticket_id !== next.ticket_id || g.previous_ticket_id === g.next_ticket_id
      || previous && g.previous_ticket_id !== previous.ticket_id || !previous && tickets.has(g.previous_ticket_id)) return false;
    const delta = previous ? instant(next.started_at)!-instant(previous.completed_at)! : undefined;
    if (g.quality === "known") {
      const gap = crmUnsigned(g.gap_us);
      if (gap === undefined || gap > instant(next.started_at)!-start || delta !== undefined && gap !== delta) return false;
      known++; visibleTotal += gap;
    } else if (g.quality === "overlapping_episodes" && g.gap_us === null && (delta === undefined || delta < 0n)) overlapping++;
    else return false;
  }
  if (known > BigInt(s.known_gap_count) || overlapping > BigInt(s.overlapping_gap_count) || visibleTotal > total) return false;
  return offset !== 0 || s.episode_count > limit || (known === BigInt(s.known_gap_count) && overlapping === BigInt(s.overlapping_gap_count) && visibleTotal === total);
}
