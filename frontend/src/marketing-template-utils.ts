import { certificationInstant as instant } from "./certification-utils";

export type TemplateContent = { name: string; channel: "email" | "sms" | "push";
  origin: "human" | "ai"; subject: string | null; body: string };
export type TemplateRequest = { template_id: string | null; previous_id: string | null;
  content: TemplateContent; reason: string; idempotency_key: string };
export type TemplateOriginal = { id: string; institute_id: string; template_id: string;
  previous_id: string | null; actor_id: string; created_at: string;
  request: TemplateRequest; content: TemplateContent };
export type TemplateCatalog = { institute_id: string; total: number; offset: number;
  limit: number; items: TemplateOriginal[] };
const record = (v: unknown): v is Record<string, unknown> => !!v && typeof v === "object" && !Array.isArray(v);
const keys = (v: unknown, expected: string[]): boolean => record(v)
  && Object.keys(v).length === expected.length && expected.every(k => Object.prototype.hasOwnProperty.call(v, k));
const literal = (v: unknown, max: number): v is string => typeof v === "string"
  && Array.from(v).length > 0 && Array.from(v).length <= max;
const text = (v: unknown, max: number): v is string => literal(v, max) && !!v.trim() && v.trim() === v;
const identifier = (v: unknown): v is string => text(v, 80);
const contentKeys = ["name", "channel", "origin", "subject", "body"];
export function validTemplateContent(value: unknown): value is TemplateContent {
  const c = value as TemplateContent;
  return keys(c, contentKeys) && text(c.name, 160) && ["email", "sms", "push"].includes(c.channel)
    && ["human", "ai"].includes(c.origin) && literal(c.body, 10000) && !!c.body.trim()
    && (c.channel === "email" ? literal(c.subject, 240) && !!c.subject.trim() : c.subject === null);
}
export const sameTemplateContent = (a: TemplateContent, b: TemplateContent): boolean =>
  contentKeys.every(k => a[k as keyof TemplateContent] === b[k as keyof TemplateContent]);
export function validTemplateRequest(value: unknown): value is TemplateRequest {
  const r = value as TemplateRequest;
  return keys(r, ["template_id", "previous_id", "content", "reason", "idempotency_key"])
    && validTemplateContent(r.content) && text(r.reason, 240) && Array.from(r.reason).length >= 3
    && text(r.idempotency_key, 120) && (r.template_id === null && r.previous_id === null
      || identifier(r.template_id) && identifier(r.previous_id));
}
export function validTemplateOriginal(value: unknown, institute: string): value is TemplateOriginal {
  const r = value as TemplateOriginal;
  return keys(r, ["id", "institute_id", "template_id", "previous_id", "actor_id", "created_at", "request", "content"])
    && identifier(r.id) && identifier(r.institute_id) && r.institute_id === institute
    && identifier(r.template_id) && text(r.actor_id, 160) && instant(r.created_at) !== undefined
    && validTemplateRequest(r.request) && validTemplateContent(r.content)
    && r.previous_id === r.request.previous_id && r.previous_id !== r.id
    && (r.request.template_id === null || r.request.template_id === r.template_id)
    && sameTemplateContent(r.content, r.request.content);
}
export function matchesTemplateReceipt(r: TemplateOriginal, terms: TemplateRequest, actor: string): boolean {
  return r.actor_id === actor && r.request.template_id === terms.template_id
    && r.request.previous_id === terms.previous_id && r.request.reason === terms.reason
    && r.request.idempotency_key === terms.idempotency_key && sameTemplateContent(r.content, terms.content);
}
export function sameTemplateOriginal(a: TemplateOriginal, b: TemplateOriginal): boolean {
  return a.id === b.id && a.institute_id === b.institute_id && a.template_id === b.template_id
    && a.previous_id === b.previous_id && instant(a.created_at) === instant(b.created_at)
    && matchesTemplateReceipt(a, b.request, b.actor_id);
}
export function validTemplateCatalog(value: unknown, institute: string, offset: number, limit: number): value is TemplateCatalog {
  const p = value as TemplateCatalog;
  return keys(p, ["institute_id", "total", "offset", "limit", "items"]) && p.institute_id === institute
    && Number.isSafeInteger(p.total) && p.total >= 0 && Number.isSafeInteger(offset) && offset >= 0
    && Number.isSafeInteger(limit) && limit >= 1 && limit <= 50 && p.offset === offset && p.limit === limit
    && Array.isArray(p.items) && p.items.length === Math.min(limit, Math.max(0, p.total - offset))
    && p.items.every(r => validTemplateOriginal(r, institute))
    && new Set(p.items.map(r => r.template_id)).size === p.items.length
    && p.items.every((r, i) => i === 0 || p.items[i - 1].template_id < r.template_id);
}
