import { certificationInstant as instant } from "./certification-utils";
import { validCampaignOriginal, type CampaignOriginal } from "./marketing-campaign-utils";
import { validDispatchIntent, validDispatchOutcome, sameDispatchTerms, type DispatchIntent, type DispatchOutcome,
  type DispatchPage } from "./marketing-dispatch-utils";

export type ConversionWindow = { start: string; end: string };
export type ConversionSelection = ConversionWindow & { intent_id: string; expected_fingerprint: string;
  authorization_id: string; accepted_outcome_id: string; ticket_id: string; reason: string; idempotency_key: string };
export type ConversionRequest = { action: "linked" | "retracted"; ticket_id: string; expected_previous_id: string | null;
  selection: ConversionSelection | null; reason: string; idempotency_key: string };
export type Attribution = { intent: DispatchIntent; authorization: CampaignOriginal; accepted: DispatchOutcome;
  ticket: { institute_id: string; customer_id: string; ticket_id: string; closed_at: string; captured_at: string;
    currency: "CHF" | "EUR" | null; amount_minor: string | null; amount_quality: "known" | "missing" | "invalid" };
  window: ConversionWindow & { institute_id: string; customer_id: string; captured_at: string };
  actor_id: string; reason: string; idempotency_key: string; basis: "explicit_manager_link";
  causal_effect_proven: false; delivery_confirmed: false };
export type ConversionOriginal = { id: string; institute_id: string; request: ConversionRequest; actor_id: string;
  created_at: string; attribution: Attribution; attribution_fingerprint: string };
export type ConversionCurrency = { mode: "test" | "live"; currency: "CHF" | "EUR"; linked_tickets: number;
  known_amount_tickets: number; missing_amount_tickets: number; invalid_amount_tickets: number; known_gross_minor: string };
export type ConversionReport = { summary: { window: ConversionWindow & { institute_id: string; campaign_id: string; captured_at: string };
  basis: "explicit_manager_links"; linked_tickets: number; live_linked_tickets: number; test_linked_tickets: number;
  unknown_currency_live_tickets: number; unknown_currency_test_tickets: number; currencies: ConversionCurrency[];
  complete_campaign_history: false; causal_effect_proven: false; delivery_confirmed: false;
  conversion_rate: null; return_on_ad_spend: null }; selected_current_links: number; full_retained_current_cohort: true;
  basis: "current_declared_links_in_observed_billing_window" };
const keys = (v: unknown, names: string[]) => !!v && typeof v === "object" && !Array.isArray(v)
  && Object.keys(v).length === names.length && names.every(k => Object.prototype.hasOwnProperty.call(v, k));
const text = (v: unknown, max = 80): v is string => typeof v === "string" && v.trim() === v && v.length > 0 && Array.from(v).length <= max;
const exact = (v: unknown, max = 160): v is string => text(v, max) && !/[\x00-\x1f\x7f]/.test(v);
const reason = (v: unknown) => text(v, 240) && Array.from(v).length >= 3;
const hash = (v: unknown) => typeof v === "string" && /^[a-f0-9]{64}$/.test(v);
const count = (v: unknown): v is number => Number.isSafeInteger(v) && (v as number) >= 0;
const unsigned = (v: unknown): v is string => typeof v === "string" && /^(0|[1-9][0-9]*)$/.test(v);
function window(v: ConversionWindow): boolean {
  return instant(v?.start) !== undefined && instant(v?.end) !== undefined && instant(v.start)! < instant(v.end)!;
}
const sameInstant = (a: string, b: string) => instant(a) !== undefined && instant(a) === instant(b);
// Every temporal field in these validated contracts is an aware typed datetime.
// Literal message/reason strings remain untouched, including date-looking strings.
function canonical(v: unknown, key = ""): string {
  if (Array.isArray(v)) return "[" + v.map(value => canonical(value)).join(",") + "]";
  if (v !== null && typeof v === "object") return "{" + Object.entries(v).sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0)
    .map(([k, value]) => canonical(k) + ":" + canonical(value, k)).join(",") + "}";
  if ((key.endsWith("_at") || key === "start" || key === "end") && typeof v === "string" && instant(v) !== undefined) {
    const us = instant(v)!, seconds = us / 1000000n - (us < 0n && us % 1000000n !== 0n ? 1n : 0n), fraction = us - seconds * 1000000n;
    v = new Date(Number(seconds * 1000n)).toISOString().slice(0, 19)
      + (fraction === 0n ? "" : "." + fraction.toString().padStart(6, "0")) + "+00:00";
  }
  return JSON.stringify(v).replace(/[\u007f-\uffff]/g, c => "\\u" + c.charCodeAt(0).toString(16).padStart(4, "0"));
}
export function validConversionSelection(v: unknown): v is ConversionSelection {
  const s = v as ConversionSelection;
  return keys(s, ["intent_id", "expected_fingerprint", "authorization_id", "accepted_outcome_id", "ticket_id", "start", "end", "reason", "idempotency_key"])
    && [s.intent_id, s.authorization_id, s.accepted_outcome_id, s.ticket_id].every(v => text(v))
    && hash(s.expected_fingerprint) && window(s) && reason(s.reason) && exact(s.idempotency_key, 120);
}
export function validConversionRequest(v: unknown): v is ConversionRequest {
  const r = v as ConversionRequest;
  if (!keys(r, ["action", "ticket_id", "expected_previous_id", "selection", "reason", "idempotency_key"]) || !text(r.ticket_id)
    || r.expected_previous_id !== null && !text(r.expected_previous_id) || !reason(r.reason) || !exact(r.idempotency_key, 120)) return false;
  return r.action === "retracted" ? r.expected_previous_id !== null && r.selection === null
    : r.action === "linked" && validConversionSelection(r.selection) && r.selection.ticket_id === r.ticket_id
      && r.selection.reason === r.reason && r.selection.idempotency_key === r.idempotency_key;
}
export async function validAttribution(v: unknown, institute: string): Promise<boolean> {
  const a = v as Attribution, t = a?.ticket, w = a?.window;
  if (!keys(a, ["intent", "authorization", "accepted", "ticket", "window", "actor_id", "reason", "idempotency_key", "basis", "causal_effect_proven", "delivery_confirmed"])
    || !await validDispatchIntent(a.intent, institute) || !await validCampaignOriginal(a.authorization, institute)
    || !await validDispatchOutcome(a.accepted, a.intent, institute) || a.accepted.request.result.status !== "accepted"
    || !exact(a.actor_id) || !exact(a.accepted.actor_id) || !exact(a.authorization.revision.actor_id) || !reason(a.reason) || !exact(a.idempotency_key, 120)
    || a.basis !== "explicit_manager_link" || a.causal_effect_proven !== false || a.delivery_confirmed !== false
    || !keys(t, ["institute_id", "customer_id", "ticket_id", "closed_at", "captured_at", "currency", "amount_minor", "amount_quality"])
    || t.institute_id !== institute || t.customer_id !== a.intent.request.customer_id || !text(t.ticket_id)
    || instant(t.closed_at) === undefined || instant(t.captured_at) === undefined || instant(t.closed_at)! > instant(t.captured_at)!
    || ![null, "CHF", "EUR"].includes(t.currency) || !["known", "missing", "invalid"].includes(t.amount_quality)
    || (t.amount_quality === "known" ? !unsigned(t.amount_minor) || t.amount_minor.length > 10 : t.amount_minor !== null)
    || !keys(w, ["institute_id", "customer_id", "start", "end", "captured_at"]) || w.institute_id !== institute || w.customer_id !== t.customer_id
    || !window(w) || !sameInstant(w.captured_at, t.captured_at) || instant(w.end)! > instant(w.captured_at)!) return false;
  const send = a.authorization.revision, approval = a.intent.submission.eligibility.campaign, observed = a.accepted.request.result.observed_at;
  return send.state === "SEND" && send.campaign_id === a.intent.request.campaign_id && send.previous_id === approval.id
    && send.id !== approval.id && sameDispatchTerms(send.content, approval.content)
    && send.reviewed_digest === approval.reviewed_digest && send.approved_digest === approval.approved_digest
    && instant(send.created_at)! >= instant(approval.created_at)! && instant(send.created_at)! <= instant(observed)!
    && instant(a.accepted.created_at)! <= instant(w.captured_at)! && instant(observed)! <= instant(w.start)!
    && instant(w.start)! <= instant(t.closed_at)! && instant(t.closed_at)! < instant(w.end)!;
}
export async function attributionFingerprint(a: Attribution): Promise<string> {
  if (!await validAttribution(a, a?.ticket?.institute_id)) throw new Error("Invalid attribution");
  const bytes = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(canonical(a)));
  return Array.from(new Uint8Array(bytes), b => b.toString(16).padStart(2, "0")).join("");
}
function matchesSelection(a: Attribution, s: ConversionSelection): boolean {
  return s.intent_id === a.intent.id && s.expected_fingerprint === a.intent.request_fingerprint && s.authorization_id === a.authorization.revision.id
    && s.accepted_outcome_id === a.accepted.id && s.ticket_id === a.ticket.ticket_id && sameInstant(s.start, a.window.start)
    && sameInstant(s.end, a.window.end) && s.reason === a.reason && s.idempotency_key === a.idempotency_key;
}
export async function validConversionOriginal(v: unknown, institute: string, ticket?: string): Promise<boolean> {
  const o = v as ConversionOriginal;
  if (!keys(o, ["id", "institute_id", "request", "actor_id", "created_at", "attribution", "attribution_fingerprint"])
    || !text(o.id) || o.institute_id !== institute || !validConversionRequest(o.request) || !exact(o.actor_id)
    || instant(o.created_at) === undefined || !hash(o.attribution_fingerprint) || o.request.expected_previous_id === o.id
    || ticket !== undefined && o.request.ticket_id !== ticket || !await validAttribution(o.attribution, institute)) return false;
  const a = o.attribution;
  return o.request.ticket_id === a.ticket.ticket_id && instant(o.created_at)! >= instant(a.window.captured_at)!
    && o.attribution_fingerprint === await attributionFingerprint(a) && (o.request.action === "retracted"
      || sameInstant(o.created_at, a.window.captured_at) && o.actor_id === a.actor_id && matchesSelection(a, o.request.selection!));
}
export function matchesConversionReceipt(o: ConversionOriginal, request: ConversionRequest, actor: string): boolean {
  return o.actor_id === actor && canonical(o.request) === canonical(request);
}
export async function sameConversionOriginal(a: unknown, b: unknown, institute: string): Promise<boolean> {
  return await validConversionOriginal(a, institute) && await validConversionOriginal(b, institute) && canonical(a) === canonical(b);
}
export async function validConversionPreview(v: unknown, institute: string, selection: ConversionSelection, actor: string): Promise<boolean> {
  const p = v as { request: ConversionSelection; attribution: Attribution; retained: false };
  return validConversionSelection(selection) && keys(p, ["request", "attribution", "retained"]) && p.retained === false && validConversionSelection(p.request)
    && canonical(p.request) === canonical(selection) && await validAttribution(p.attribution, institute)
    && p.attribution.actor_id === actor && matchesSelection(p.attribution, selection);
}
function pageBounds(v: unknown, institute: string, offset: number, limit: number): v is DispatchPage<ConversionOriginal> {
  const p = v as DispatchPage<ConversionOriginal>;
  return keys(p, ["institute_id", "total", "offset", "limit", "items"]) && p.institute_id === institute && count(p.total)
    && count(offset) && Number.isSafeInteger(limit) && limit >= 1 && limit <= 50 && p.offset === offset && p.limit === limit
    && Array.isArray(p.items) && p.items.length === Math.min(limit, Math.max(0, p.total - offset));
}
function compare(a: string, b: string): number {
  const x = Array.from(a, c => c.codePointAt(0)!), y = Array.from(b, c => c.codePointAt(0)!);
  for (let i = 0; i < Math.min(x.length, y.length); i++) if (x[i] !== y[i]) return x[i] - y[i];
  return x.length - y.length;
}
export async function validCurrentConversionPage(v: unknown, institute: string, campaign: string, period: ConversionWindow, offset: number, limit: number): Promise<boolean> {
  if (!window(period) || !text(campaign) || !pageBounds(v, institute, offset, limit)) return false;
  const ids = new Set<string>(), tickets = new Set<string>(), operations = new Set<string>(); let previous: string | undefined;
  for (const o of v.items) {
    if (!await validConversionOriginal(o, institute) || o.request.action !== "linked" || o.attribution.intent.request.campaign_id !== campaign
      || instant(o.attribution.ticket.closed_at)! < instant(period.start)! || instant(o.attribution.ticket.closed_at)! >= instant(period.end)!
      || ids.has(o.id) || tickets.has(o.request.ticket_id) || operations.has(o.request.idempotency_key)
      || previous !== undefined && compare(previous, o.request.ticket_id) >= 0) return false;
    ids.add(o.id); tickets.add(o.request.ticket_id); operations.add(o.request.idempotency_key); previous = o.request.ticket_id;
  }
  return true;
}
export async function validConversionAuditPage(v: unknown, institute: string, ticket: string, offset: number, limit: number): Promise<boolean> {
  if (!text(ticket) || !pageBounds(v, institute, offset, limit)) return false;
  const originals = new Map<string, ConversionOriginal>(), operations = new Set<string>(); let previous: ConversionOriginal | undefined;
  for (const o of v.items) {
    if (!await validConversionOriginal(o, institute, ticket) || originals.has(o.id) || operations.has(o.request.idempotency_key) || previous && (instant(previous.created_at)! > instant(o.created_at)!
      || sameInstant(previous.created_at, o.created_at) && compare(previous.id, o.id) >= 0)) return false;
    originals.set(o.id, o); operations.add(o.request.idempotency_key); previous = o;
  }
  for (const o of originals.values()) {
    const seen = new Set<string>(); let cursor: ConversionOriginal | undefined = o;
    while (cursor) { if (seen.has(cursor.id)) return false; seen.add(cursor.id);
      cursor = cursor.request.expected_previous_id === null ? undefined : originals.get(cursor.request.expected_previous_id); }
    const prior = o.request.expected_previous_id === null ? undefined : originals.get(o.request.expected_previous_id);
    if (prior && (instant(prior.created_at)! > instant(o.created_at)! || o.request.action === "retracted"
      && (prior.request.action !== "linked" || canonical(prior.attribution) !== canonical(o.attribution)))) return false;
  }
  // An ancestor outside this bounded page still requires an independent original read.
  return true;
}
export function validConversionReport(v: unknown, institute: string, campaign: string, period: ConversionWindow): v is ConversionReport {
  const r = v as ConversionReport, s = r?.summary, w = s?.window;
  if (!window(period) || !text(campaign) || !keys(r, ["summary", "selected_current_links", "full_retained_current_cohort", "basis"])
    || r.full_retained_current_cohort !== true || r.basis !== "current_declared_links_in_observed_billing_window"
    || !keys(s, ["window", "basis", "linked_tickets", "live_linked_tickets", "test_linked_tickets", "unknown_currency_live_tickets", "unknown_currency_test_tickets",
      "currencies", "complete_campaign_history", "causal_effect_proven", "delivery_confirmed", "conversion_rate", "return_on_ad_spend"])
    || !keys(w, ["institute_id", "campaign_id", "start", "end", "captured_at"]) || w.institute_id !== institute || w.campaign_id !== campaign
    || !window(w) || !sameInstant(w.start, period.start) || !sameInstant(w.end, period.end) || instant(w.captured_at) === undefined || instant(w.end)! > instant(w.captured_at)!
    || s.basis !== "explicit_manager_links" || s.complete_campaign_history !== false || s.causal_effect_proven !== false || s.delivery_confirmed !== false
    || s.conversion_rate !== null || s.return_on_ad_spend !== null || !Array.isArray(s.currencies)
    || ![r.selected_current_links, s.linked_tickets, s.live_linked_tickets, s.test_linked_tickets, s.unknown_currency_live_tickets, s.unknown_currency_test_tickets].every(count)
    || r.selected_current_links !== s.linked_tickets || BigInt(s.linked_tickets) !== BigInt(s.live_linked_tickets) + BigInt(s.test_linked_tickets)) return false;
  const totals = { live: BigInt(s.unknown_currency_live_tickets), test: BigInt(s.unknown_currency_test_tickets) }; let previous = "";
  for (const c of s.currencies) {
    if (!keys(c, ["mode", "currency", "linked_tickets", "known_amount_tickets", "missing_amount_tickets", "invalid_amount_tickets", "known_gross_minor"])
      || !["live", "test"].includes(c.mode) || !["CHF", "EUR"].includes(c.currency) || !unsigned(c.known_gross_minor)
      || ![c.linked_tickets, c.known_amount_tickets, c.missing_amount_tickets, c.invalid_amount_tickets].every(count) || c.linked_tickets === 0
      || BigInt(c.linked_tickets) !== BigInt(c.known_amount_tickets) + BigInt(c.missing_amount_tickets) + BigInt(c.invalid_amount_tickets)
      || BigInt(c.known_gross_minor) > BigInt(c.known_amount_tickets) * 9999999999n
      || previous >= c.mode + "/" + c.currency) return false;
    previous = c.mode + "/" + c.currency; totals[c.mode] += BigInt(c.linked_tickets);
  }
  return totals.live === BigInt(s.live_linked_tickets) && totals.test === BigInt(s.test_linked_tickets);
}
