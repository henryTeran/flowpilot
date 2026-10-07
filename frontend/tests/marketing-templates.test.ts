import test from "node:test";
import assert from "node:assert/strict";
import { validTemplateContent, validTemplateRequest, validTemplateOriginal, validTemplateCatalog,
  matchesTemplateReceipt, sameTemplateOriginal, type TemplateOriginal } from "../src/marketing-template-utils";
const original = (): TemplateOriginal => ({ id: "revision-a", institute_id: "own", template_id: "root-a",
  previous_id: null, actor_id: "manager", created_at: "2026-10-07T10:00:00.123456Z",
  request: { template_id: null, previous_id: null, content: { name: "Relance", channel: "email", origin: "ai",
    subject: " Bonjour ", body: "Bonjour {customer_name}\n🙂" }, reason: "Validation explicite", idempotency_key: "key-a" },
  content: { name: "Relance", channel: "email", origin: "ai", subject: " Bonjour ", body: "Bonjour {customer_name}\n🙂" } });
test("literal template content supports every channel/origin and Python Unicode bounds", () => {
  for (const channel of ["email", "sms", "push"] as const) for (const origin of ["human", "ai"] as const) {
    assert.equal(validTemplateContent({ ...original().content, channel, origin, subject: channel === "email" ? "Sujet" : null }), true);
  }
  assert.equal(validTemplateContent({ ...original().content, body: "🙂".repeat(10000) }), true);
  for (const patch of [{ body: "🙂".repeat(10001) }, { body: " \n" }, { name: " Relance" },
    { subject: null }, { subject: " " }, { channel: "sms" }, { origin: "unknown" }, { extra: true }]) {
    assert.equal(validTemplateContent({ ...original().content, ...patch }), false);
  }
});
test("original receipt pins scope, full literal request, actor and microsecond clock", () => {
  const a = original(); assert.equal(validTemplateOriginal(a, "own"), true);
  assert.equal(matchesTemplateReceipt(a, a.request, "manager"), true);
  assert.equal(matchesTemplateReceipt(a, a.request, "other"), false);
  assert.equal(matchesTemplateReceipt(a, { ...a.request, content: { ...a.content, body: "Changed" } }, "manager"), false);
  const alternate = { ...a, created_at: "2026-10-07T12:00:00.123456+02:00" };
  assert.equal(sameTemplateOriginal(a, alternate), true);
  assert.equal(sameTemplateOriginal(a, { ...a, created_at: "2026-10-07T10:00:00.123457Z" }), false);
  for (const patch of [{ institute_id: "foreign" }, { previous_id: a.id }, { created_at: "2026-10-07" },
    { content: { ...a.content, body: "Forged" } }, { request: { ...a.request, template_id: "foreign" } },
    { request: { ...a.request, previous_id: "previous" } }, { actor_id: " manager" }, { external_message_sent: true }]) {
    assert.equal(validTemplateOriginal({ ...a, ...patch }, "own"), false);
  }
  const correction = { ...a, id: "revision-b", previous_id: a.id,
    request: { ...a.request, template_id: a.template_id, previous_id: a.id } };
  assert.equal(validTemplateOriginal(correction, "own"), true);
  assert.equal(validTemplateRequest({ ...a.request, template_id: a.template_id }), false);
});
test("catalog refuses wrong bounds, totals, duplicated roots, ordering and foreign originals", () => {
  const a = original(), b = { ...original(), id: "revision-b", template_id: "root-b" };
  const p = { institute_id: "own", total: 2, offset: 0, limit: 20, items: [a, b] };
  assert.equal(validTemplateCatalog(p, "own", 0, 20), true);
  for (const patch of [{ total: 3 }, { total: 1 }, { offset: 1 }, { limit: 50 }, { items: [b, a] },
    { items: [a, a] }, { items: [a, { ...b, institute_id: "foreign" }] }, { total: Number.MAX_SAFE_INTEGER + 1 }]) {
    assert.equal(validTemplateCatalog({ ...p, ...patch }, "own", 0, 20), false);
  }
  assert.equal(validTemplateCatalog({ ...p, offset: 2, items: [] }, "own", 2, 20), true);
  assert.equal(validTemplateCatalog(p, "own", 0, 51), false);
  assert.equal(validTemplateCatalog(null, "own", 0, 20), false);
});
