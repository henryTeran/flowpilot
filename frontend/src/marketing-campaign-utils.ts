import { certificationInstant as instant } from "./certification-utils";
import { validTemplateContent, type TemplateContent } from "./marketing-template-utils";

export type CampaignContent = Omit<TemplateContent, "name"> & { institute_id: string; template_original_id: string | null;
  audience: { id: string; institute_id: string; captured_at: string; customer_ids: string[] } };
export type CampaignTermsContent = Omit<CampaignContent, "institute_id" | "audience"> & { audience_id: string };
export type CampaignRequest = { action: "create" | "edit" | "review" | "approve" | "send"; campaign_id: string | null;
  expected_revision_id: string | null; content: CampaignTermsContent | null; reason: string; idempotency_key: string };
export type CampaignRevision = { id: string; campaign_id: string; institute_id: string; previous_id: string | null;
  state: "DRAFT" | "REVIEW" | "APPROVE" | "SEND"; content: CampaignContent; actor_id: string; reason: string; created_at: string;
  reviewed_digest: string | null; approved_digest: string | null; external_message_sent: false; delivery_authorized: false };
export type CampaignOriginal = { request: CampaignRequest; revision: CampaignRevision };
export type CampaignAuditPage = { institute_id: string; campaign_id: string; total: number; offset: number;
  limit: number; originals: CampaignOriginal[] };
const text = (v: unknown, max = 80): v is string => typeof v === "string" && !!v.trim() && v.trim() === v && Array.from(v).length <= max;
const keys = (v: unknown, expected: string[]) => !!v && typeof v === "object" && !Array.isArray(v)
  && Object.keys(v).length === expected.length && expected.every(k => Object.prototype.hasOwnProperty.call(v, k));
function message(v: CampaignTermsContent | CampaignContent): boolean {
  return validTemplateContent({ name: "Campaign content", channel: v.channel, origin: v.origin, subject: v.subject, body: v.body })
    && (v.template_original_id === null || text(v.template_original_id));
}
export function validCampaignContent(v: unknown, institute: string): v is CampaignContent {
  const c = v as CampaignContent, a = c?.audience;
  return keys(c, ["institute_id", "channel", "origin", "subject", "body", "template_original_id", "audience"])
    && c.institute_id === institute && message(c) && keys(a, ["id", "institute_id", "captured_at", "customer_ids"])
    && text(a.id) && a.institute_id === institute && instant(a.captured_at) !== undefined
    && Array.isArray(a.customer_ids) && a.customer_ids.length > 0 && a.customer_ids.every(id => text(id))
    && new Set(a.customer_ids).size === a.customer_ids.length;
}
export function validCampaignRequest(v: unknown): v is CampaignRequest {
  const r = v as CampaignRequest;
  if (!keys(r, ["action", "campaign_id", "expected_revision_id", "content", "reason", "idempotency_key"])
    || !text(r.reason, 240) || Array.from(r.reason).length < 3 || !text(r.idempotency_key, 120)) return false;
  if (r.content !== null && (!keys(r.content, ["channel", "origin", "subject", "body", "audience_id", "template_original_id"])
    || !message(r.content) || !text(r.content.audience_id))) return false;
  return r.action === "create" ? r.campaign_id === null && r.expected_revision_id === null && r.content !== null
    : ["edit", "review", "approve", "send"].includes(r.action) && text(r.campaign_id) && text(r.expected_revision_id)
      && (r.action === "edit" ? r.content !== null : r.content === null);
}
function utcPython(value: string): string {
  const us = instant(value)!;
  const seconds = us / 1000000n - (us < 0n && us % 1000000n !== 0n ? 1n : 0n);
  const fraction = us - seconds * 1000000n;
  return new Date(Number(seconds * 1000n)).toISOString().slice(0, 19)
    + (fraction === 0n ? "" : "." + fraction.toString().padStart(6, "0")) + "+00:00";
}
function canonical(v: unknown): string {
  if (Array.isArray(v)) return "[" + v.map(canonical).join(",") + "]";
  if (v !== null && typeof v === "object") return "{" + Object.entries(v).sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0)
    .map(([k, value]) => canonical(k) + ":" + canonical(value)).join(",") + "}";
  return JSON.stringify(v).replace(/[\u007f-\uffff]/g, c => "\\u" + c.charCodeAt(0).toString(16).padStart(4, "0"));
}
export async function campaignDigest(content: CampaignContent): Promise<string> {
  if (!validCampaignContent(content, content?.institute_id)) throw new Error("Invalid campaign content");
  const normalized = { ...content, audience: { ...content.audience, captured_at: utcPython(content.audience.captured_at) } };
  const bytes = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(canonical(normalized)));
  return Array.from(new Uint8Array(bytes), b => b.toString(16).padStart(2, "0")).join("");
}
export async function validCampaignOriginal(v: unknown, institute: string): Promise<boolean> {
  const o = v as CampaignOriginal, r = o?.revision;
  if (!keys(o, ["request", "revision"]) || !validCampaignRequest(o.request)
    || !keys(r, ["id", "campaign_id", "institute_id", "previous_id", "state", "content", "actor_id", "reason", "created_at",
      "reviewed_digest", "approved_digest", "external_message_sent", "delivery_authorized"])
    || !text(r.id) || !text(r.campaign_id) || r.institute_id !== institute || !text(r.actor_id, 160)
    || !validCampaignContent(r.content, institute) || instant(r.created_at) === undefined
    || instant(r.content.audience.captured_at)! > instant(r.created_at)! || r.external_message_sent !== false || r.delivery_authorized !== false
    || r.previous_id === r.id || r.previous_id !== o.request.expected_revision_id || r.reason !== o.request.reason
    || o.request.campaign_id !== null && o.request.campaign_id !== r.campaign_id) return false;
  const state = { create: "DRAFT", edit: "DRAFT", review: "REVIEW", approve: "APPROVE", send: "SEND" }[o.request.action];
  if (r.state !== state) return false;
  const c = o.request.content;
  if (c !== null && (c.audience_id !== r.content.audience.id || c.template_original_id !== r.content.template_original_id
    || c.channel !== r.content.channel || c.origin !== r.content.origin || c.subject !== r.content.subject || c.body !== r.content.body)) return false;
  if (r.state === "DRAFT") return r.reviewed_digest === null && r.approved_digest === null;
  const digest = await campaignDigest(r.content);
  return r.reviewed_digest === digest && (r.state === "REVIEW" ? r.approved_digest === null : r.approved_digest === digest);
}
export function matchesCampaignReceipt(o: CampaignOriginal, request: CampaignRequest, actor: string): boolean {
  return o.revision.actor_id === actor && canonical(o.request) === canonical(request);
}
export async function sameCampaignOriginal(a: CampaignOriginal, b: CampaignOriginal, institute: string): Promise<boolean> {
  if (!await validCampaignOriginal(a, institute) || !await validCampaignOriginal(b, institute)) return false;
  const normalize = (o: CampaignOriginal) => ({ ...o, revision: { ...o.revision, created_at: utcPython(o.revision.created_at),
    content: { ...o.revision.content, audience: { ...o.revision.content.audience, captured_at: utcPython(o.revision.content.audience.captured_at) } } } });
  return canonical(normalize(a)) === canonical(normalize(b));
}
export async function validCampaignCatalog(v: unknown, institute: string, offset: number, limit: number): Promise<boolean> {
  const p = v as { institute_id: string; total: number; offset: number; limit: number; items: CampaignOriginal[] };
  if (!keys(p, ["institute_id", "total", "offset", "limit", "items"]) || p.institute_id !== institute
    || !Number.isSafeInteger(p.total) || p.total < 0 || !Number.isSafeInteger(offset) || offset < 0
    || !Number.isSafeInteger(limit) || limit < 1 || limit > 50 || p.offset !== offset || p.limit !== limit
    || !Array.isArray(p.items) || p.items.length !== Math.min(limit, Math.max(0, p.total - offset))) return false;
  for (let i = 0; i < p.items.length; i++) {
    if (!await validCampaignOriginal(p.items[i], institute)
      || i > 0 && p.items[i - 1].revision.campaign_id >= p.items[i].revision.campaign_id) return false;
  }
  return true;
}
export async function validCampaignAuditPage(v: unknown, institute: string, campaign: string, offset: number, limit: number): Promise<boolean> {
  const p = v as CampaignAuditPage;
  if (!keys(p, ["institute_id", "campaign_id", "total", "offset", "limit", "originals"])
    || p.institute_id !== institute || p.campaign_id !== campaign || !text(campaign)
    || !Number.isSafeInteger(p.total) || p.total < 1 || !Number.isSafeInteger(offset) || offset < 0
    || !Number.isSafeInteger(limit) || limit < 1 || limit > 50 || p.offset !== offset || p.limit !== limit
    || !Array.isArray(p.originals) || p.originals.length !== Math.min(limit, Math.max(0, p.total - offset))) return false;
  const originals = new Map<string, CampaignOriginal>();
  for (let i = 0; i < p.originals.length; i++) {
    const o = p.originals[i], prior = p.originals[i - 1]?.revision;
    if (!await validCampaignOriginal(o, institute) || o.revision.campaign_id !== campaign || originals.has(o.revision.id)) return false;
    if (prior && (instant(prior.created_at)! > instant(o.revision.created_at)!
      || instant(prior.created_at) === instant(o.revision.created_at) && prior.id >= o.revision.id)) return false;
    originals.set(o.revision.id, o);
  }
  // Equal-clock ID order is display order; only explicit predecessor IDs convey causality.
  for (const o of p.originals) {
    const visited = new Set<string>();
    let cursor: CampaignOriginal | undefined = o;
    while (cursor) {
      if (visited.has(cursor.revision.id)) return false;
      visited.add(cursor.revision.id);
      cursor = cursor.revision.previous_id === null ? undefined : originals.get(cursor.revision.previous_id);
    }
    const previous = o.revision.previous_id === null ? undefined : originals.get(o.revision.previous_id);
    if (!previous) continue; // A bounded page need not contain its predecessor.
    if (instant(previous.revision.created_at)! > instant(o.revision.created_at)!) return false;
    if (o.request.action === "review" || o.request.action === "approve" || o.request.action === "send") {
      if (previous.revision.state !== (o.request.action === "review" ? "DRAFT" : o.request.action === "approve" ? "REVIEW" : "APPROVE")
        || await campaignDigest(previous.revision.content) !== await campaignDigest(o.revision.content)) return false;
    }
  }
  return true;
}
