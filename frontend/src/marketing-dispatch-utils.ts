import { certificationInstant as instant } from "./certification-utils";
import { campaignDigest, validCampaignContent, type CampaignRevision } from "./marketing-campaign-utils";
import { validContactOriginal, type ContactOriginal, type ContactChannel } from "./marketing-contact-utils";
export type DispatchAccount = { institute_id: string; provider: string; account_id: string; channel: ContactChannel;
  sender_id: string; mode: "live" | "test"; push_application: string | null };
export type DispatchRequest = { campaign_id: string; expected_revision_id: string; customer_id: string; expected_contact_id: string;
  account_id: string; reason: string; idempotency_key: string };
export type DispatchSubmission = { account: DispatchAccount; actor_id: string; idempotency_key: string; eligibility: {
  customer: { institute_id: string; customer_id: string; created_at: string }; campaign: CampaignRevision; original: ContactOriginal;
  captured_at: string; reason: "declared_eligible"; eligible_by_current_declaration: true; delivery_authorized: false; external_message_sent: false } };
export type DispatchIntent = { id: string; request: DispatchRequest; submission: DispatchSubmission; created_at: string; request_fingerprint: string };
export type DispatchResult = { account: DispatchAccount; idempotency_key: string; request_fingerprint: string;
  status: "accepted" | "rejected" | "unknown"; provider_message_id: string | null; observed_at: string; delivery_confirmed: false };
export type DispatchOutcome = { id: string; actor_id: string; created_at: string; request: { intent_id: string;
  expected_previous_id: string | null; result: DispatchResult; reason: string; idempotency_key: string } };
export type DispatchPage<T> = { institute_id: string; total: number; offset: number; limit: number; items: T[] };
const keys = (v: unknown, names: string[]) => !!v && typeof v === "object" && !Array.isArray(v)
  && Object.keys(v).length === names.length && names.every(k => Object.prototype.hasOwnProperty.call(v, k));
const text = (v: unknown, max: number): v is string => typeof v === "string" && !!v.trim() && v.trim() === v && Array.from(v).length <= max;
const exact = (v: unknown, max: number): v is string => text(v, max) && !/[\x00-\x1f\x7f]/.test(v);
const count = (v: unknown): v is number => Number.isSafeInteger(v) && (v as number) >= 0;
const reason = (v: unknown) => text(v, 240) && Array.from(v).length >= 3;
const hash = (v: unknown) => typeof v === "string" && /^[a-f0-9]{64}$/.test(v);
export function validDispatchAccount(v: unknown, institute: string, channel?: ContactChannel): v is DispatchAccount {
  const a = v as DispatchAccount;
  return keys(a, ["institute_id", "provider", "account_id", "channel", "sender_id", "mode", "push_application"])
    && a.institute_id === institute && text(a.institute_id, 80) && exact(a.provider, 160) && exact(a.account_id, 160) && exact(a.sender_id, 160)
    && ["email", "sms", "push"].includes(a.channel) && (channel === undefined || a.channel === channel) && ["live", "test"].includes(a.mode)
    && (a.channel === "push" ? exact(a.push_application, 160) : a.push_application === null);
}
// Python orders Unicode code points, rather than UTF-16 code units.
function compare(a: string, b: string): number {
  const left = Array.from(a, c => c.codePointAt(0)!), right = Array.from(b, c => c.codePointAt(0)!);
  for (let i = 0; i < Math.min(left.length, right.length); i++) if (left[i] !== right[i]) return left[i] - right[i];
  return left.length - right.length;
}
function pageBounds(v: unknown, institute: string, offset: number, limit: number): v is DispatchPage<unknown> {
  const p = v as DispatchPage<unknown>;
  return text(institute, 80) && keys(p, ["institute_id", "total", "offset", "limit", "items"]) && p.institute_id === institute && count(p.total)
    && count(offset) && count(limit) && limit >= 1 && limit <= 50 && p.offset === offset && p.limit === limit
    && Array.isArray(p.items) && p.items.length === Math.min(limit, Math.max(0, p.total - offset));
}
export function validDispatchAccountPage(v: unknown, institute: string, channel: ContactChannel, offset: number, limit: number): boolean {
  if (!["email", "sms", "push"].includes(channel) || !pageBounds(v, institute, offset, limit)) return false;
  return v.items.every((a, index) => validDispatchAccount(a, institute, channel)
    && (index === 0 || compare((v.items[index - 1] as DispatchAccount).account_id, a.account_id) < 0));
}
export function validDispatchRequest(v: unknown): v is DispatchRequest {
  const r = v as DispatchRequest;
  return keys(r, ["campaign_id", "expected_revision_id", "customer_id", "expected_contact_id", "account_id", "reason", "idempotency_key"])
    && [r.campaign_id, r.expected_revision_id, r.customer_id, r.expected_contact_id].every(v => text(v, 80))
    && exact(r.account_id, 160) && reason(r.reason) && exact(r.idempotency_key, 120);
}
function utc(value: string): string {
  const us = instant(value)!;
  const seconds = us / 1000000n - (us < 0n && us % 1000000n !== 0n ? 1n : 0n), fraction = us - seconds * 1000000n;
  return new Date(Number(seconds * 1000n)).toISOString().slice(0, 19)
    + (fraction === 0n ? "" : "." + fraction.toString().padStart(6, "0")) + "+00:00";
}
function canonical(v: unknown, key = ""): string {
  if (Array.isArray(v)) return "[" + v.map(value => canonical(value)).join(",") + "]";
  if (v !== null && typeof v === "object") return "{" + Object.entries(v).sort(([a], [b]) => compare(a, b))
    .map(([k, value]) => canonical(k) + ":" + canonical(value, k)).join(",") + "}";
  if (key.endsWith("_at") && typeof v === "string" && instant(v) !== undefined) v = utc(v);
  return JSON.stringify(v).replace(/[\u007f-\uffff]/g, c => "\\u" + c.charCodeAt(0).toString(16).padStart(4, "0"));
}
async function validSubmission(v: unknown, institute: string): Promise<boolean> {
  const s = v as DispatchSubmission, e = s?.eligibility, c = e?.campaign, customer = e?.customer, o = e?.original;
  if (!keys(s, ["account", "actor_id", "idempotency_key", "eligibility"]) || !validDispatchAccount(s.account, institute)
    || !exact(s.actor_id, 160) || !exact(s.idempotency_key, 120)
    || !keys(e, ["customer", "campaign", "original", "captured_at", "reason", "eligible_by_current_declaration", "delivery_authorized", "external_message_sent"])
    || !keys(customer, ["institute_id", "customer_id", "created_at"]) || customer.institute_id !== institute || !text(customer.customer_id, 80)
    || instant(customer.created_at) === undefined || instant(e.captured_at) === undefined
    || !keys(c, ["id", "campaign_id", "institute_id", "previous_id", "state", "content", "actor_id", "reason", "created_at", "reviewed_digest", "approved_digest", "external_message_sent", "delivery_authorized"])
    || !text(c.id, 80) || !text(c.campaign_id, 80) || !text(c.previous_id, 80) || c.previous_id === c.id || c.institute_id !== institute
    || c.state !== "APPROVE" || !text(c.actor_id, 160) || !reason(c.reason) || instant(c.created_at) === undefined
    || !validCampaignContent(c.content, institute) || c.content.channel !== s.account.channel || c.external_message_sent !== false || c.delivery_authorized !== false
    || !validContactOriginal(o, institute, customer.customer_id) || e.reason !== "declared_eligible" || e.eligible_by_current_declaration !== true
    || e.delivery_authorized !== false || e.external_message_sent !== false || !c.content.audience.customer_ids.includes(customer.customer_id)
    || instant(c.content.audience.captured_at)! > instant(c.created_at)! || instant(c.created_at)! > instant(e.captured_at)!
    || instant(customer.created_at)! > instant(e.captured_at)! || instant(o.created_at)! > instant(e.captured_at)!) return false;
  const communication = o.declaration.communications.find(value => value.channel === s.account.channel)!;
  if (communication.permission !== "granted" || communication.destination === null
    || s.account.channel === "push" && communication.destination.push_application !== s.account.push_application) return false;
  const digest = await campaignDigest(c.content);
  return c.reviewed_digest === digest && c.approved_digest === digest;
}
export async function dispatchFingerprint(submission: DispatchSubmission): Promise<string> {
  if (!await validSubmission(submission, submission?.account?.institute_id)) throw new Error("Invalid dispatch submission");
  const bytes = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(canonical(submission)));
  return Array.from(new Uint8Array(bytes), b => b.toString(16).padStart(2, "0")).join("");
}
export async function validDispatchIntent(v: unknown, institute: string): Promise<boolean> {
  const i = v as DispatchIntent;
  if (!keys(i, ["id", "request", "submission", "created_at", "request_fingerprint"]) || !text(i.id, 80)
    || !validDispatchRequest(i.request) || instant(i.created_at) === undefined || !hash(i.request_fingerprint)
    || !await validSubmission(i.submission, institute)) return false;
  const r = i.request, s = i.submission, e = s.eligibility;
  return r.campaign_id === e.campaign.campaign_id && r.expected_revision_id === e.campaign.id && r.customer_id === e.customer.customer_id
    && r.expected_contact_id === e.original.id && r.account_id === s.account.account_id && r.idempotency_key === s.idempotency_key
    && instant(i.created_at) === instant(e.captured_at) && i.request_fingerprint === await dispatchFingerprint(s);
}
export function sameDispatchTerms(a: unknown, b: unknown): boolean { return canonical(a) === canonical(b); }
export function matchesDispatchReceipt(intent: DispatchIntent, request: DispatchRequest, actor: string, account: DispatchAccount): boolean {
  return intent.submission.actor_id === actor && sameDispatchTerms(intent.request, request) && sameDispatchTerms(intent.submission.account, account);
}
export async function sameDispatchIntent(a: unknown, b: unknown, institute: string): Promise<boolean> {
  return await validDispatchIntent(a, institute) && await validDispatchIntent(b, institute) && sameDispatchTerms(a, b);
}
export async function validDispatchIntentPage(v: unknown, institute: string, campaign: string, offset: number, limit: number): Promise<boolean> {
  if (!text(campaign, 80) || !pageBounds(v, institute, offset, limit)) return false;
  const ids = new Set<string>(); let previous: DispatchIntent | undefined;
  for (const value of v.items) {
    if (!await validDispatchIntent(value, institute)) return false;
    const i = value as DispatchIntent;
    if (i.request.campaign_id !== campaign || ids.has(i.id) || previous && (instant(previous.created_at)! > instant(i.created_at)!
      || instant(previous.created_at) === instant(i.created_at) && compare(previous.id, i.id) >= 0)) return false;
    ids.add(i.id); previous = i;
  }
  return true;
}
export async function validDispatchOutcome(v: unknown, intent: DispatchIntent, institute: string): Promise<boolean> {
  const o = v as DispatchOutcome, q = o?.request, r = q?.result;
  if (!await validDispatchIntent(intent, institute) || !keys(o, ["id", "actor_id", "created_at", "request"])
    || !text(o.id, 80) || !exact(o.actor_id, 160) || instant(o.created_at) === undefined
    || !keys(q, ["intent_id", "expected_previous_id", "result", "reason", "idempotency_key"]) || q.intent_id !== intent.id
    || q.expected_previous_id !== null && (!text(q.expected_previous_id, 80) || q.expected_previous_id === o.id)
    || !reason(q.reason) || !text(q.idempotency_key, 120)
    || !keys(r, ["account", "idempotency_key", "request_fingerprint", "status", "provider_message_id", "observed_at", "delivery_confirmed"])
    || !validDispatchAccount(r.account, institute) || !sameDispatchTerms(r.account, intent.submission.account)
    || r.idempotency_key !== intent.request.idempotency_key || r.request_fingerprint !== intent.request_fingerprint
    || !["accepted", "rejected", "unknown"].includes(r.status) || r.delivery_confirmed !== false || instant(r.observed_at) === undefined
    || r.provider_message_id !== null && !exact(r.provider_message_id, 240) || r.status === "accepted" && r.provider_message_id === null) return false;
  return instant(o.created_at)! >= instant(intent.created_at)! && instant(r.observed_at)! >= instant(intent.created_at)!
    && instant(r.observed_at)! <= instant(o.created_at)!;
}
export async function validDispatchOutcomePage(v: unknown, intent: DispatchIntent, institute: string, offset: number, limit: number): Promise<boolean> {
  if (!pageBounds(v, institute, offset, limit)) return false;
  const originals = new Map<string, DispatchOutcome>(); let previous: DispatchOutcome | undefined;
  for (const value of v.items) {
    if (!await validDispatchOutcome(value, intent, institute)) return false;
    const o = value as DispatchOutcome;
    if (originals.has(o.id) || previous && (instant(previous.created_at)! > instant(o.created_at)!
      || instant(previous.created_at) === instant(o.created_at) && compare(previous.id, o.id) >= 0)) return false;
    originals.set(o.id, o); previous = o;
  }
  for (const o of originals.values()) {
    const visited = new Set<string>(); let cursor: DispatchOutcome | undefined = o;
    while (cursor) { if (visited.has(cursor.id)) return false; visited.add(cursor.id);
      cursor = cursor.request.expected_previous_id === null ? undefined : originals.get(cursor.request.expected_previous_id); }
    const prior = o.request.expected_previous_id === null ? undefined : originals.get(o.request.expected_previous_id);
    if (prior && (prior.request.result.status !== "unknown" || instant(prior.created_at)! > instant(o.created_at)!
      || instant(prior.request.result.observed_at)! > instant(o.request.result.observed_at)!
      || prior.request.result.provider_message_id !== null && prior.request.result.provider_message_id !== o.request.result.provider_message_id)) return false;
  }
  return true;
}
